from __future__ import annotations
 
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
 
import requests
 
logger = logging.getLogger(__name__)
 
# ── STAC config ──────────────────────────────────────────────────────────────
STAC_SEARCH   = "https://earth-search.aws.element84.com/v1/search"
COLLECTION    = "sentinel-2-l2a"
MAX_CLOUD_PCT = 30       # reject scenes with >30 % cloud cover
LOOKBACK_DAYS = 30       # Sentinel-2 revisit ≈ 5 days; 30 days gives 6 passes
BBOX_HALF_DEG = 0.01     # ±0.01° ≈ 1 km box around target point
 
# ── NDVI thresholds for semi-arid Rajasthan (Kharif/Rabi context) ────────────
#   > 0.55  dense, healthy canopy      → stress = 0.0
#   0.55–0.20  moderate → stressed     → linear ramp
#   < 0.20  bare soil / failed crop    → stress = 1.0
NDVI_HEALTHY  = 0.55
NDVI_STRESSED = 0.20
 
# ── In-memory cache ───────────────────────────────────────────────────────────
_CACHE:      dict[str, dict] = {}
_CACHE_LOCK: threading.Lock  = threading.Lock()
CACHE_TTL_H = 12    # 12 h — well within the 5-day Sentinel revisit window
 
 
# ═══════════════════════════════ public API ═══════════════════════════════════
 
def fetch_ndvi_risk_score(
    lat: float,
    lon: float,
    timeout_seconds: float = 8.0,
) -> Optional[float]:
    """
    Return normalised crop-stress score in [0.0, 1.0], or None on failure.
    Cached per-point for CACHE_TTL_H hours.
    """
    key    = f"{lat:.4f},{lon:.4f}"
    cached = _get_cached(key)
    if cached is not None:
        return cached
 
    try:
        score = _compute(lat, lon, timeout_seconds)
    except Exception as exc:
        logger.warning("NDVI fetch failed (%.4f, %.4f): %s", lat, lon, exc)
        score = None
 
    if score is not None:
        _set_cached(key, score)
    return score
 
 
def fetch_ndvi_detail(
    lat: float,
    lon: float,
    timeout_seconds: float = 8.0,
) -> Optional[dict]:
    """
    Extended payload for /signals/ndvi transparency endpoint.
    Returns raw NDVI, stress score, scene date, cloud %, and source info.
    """
    try:
        item = _find_best_scene(lat, lon, timeout_seconds)
        if not item:
            return None
        props      = item.get("properties", {})
        ndvi_raw   = _sample_ndvi(item, lat, lon)
        cloud_pct  = props.get("eo:cloud_cover", 0)
        scene_date = props.get("datetime", "")[:10]
        stress     = _ndvi_to_stress(ndvi_raw) if ndvi_raw is not None else None
 
        return {
            "ndvi_raw":        ndvi_raw,
            "stress_score":    stress,
            "scene_date":      scene_date,
            "cloud_cover_pct": cloud_pct,
            "scene_id":        item.get("id"),
            "source":          "Sentinel-2 L2A via Element84 Earth Search",
            "location":        {"lat": lat, "lon": lon},
        }
    except Exception as exc:
        logger.warning("NDVI detail failed: %s", exc)
        return None
 
 
# ═══════════════════════════════ internals ════════════════════════════════════
 
def _compute(lat: float, lon: float, timeout: float) -> Optional[float]:
    item = _find_best_scene(lat, lon, timeout)
    if not item:
        return None
 
    ndvi_raw = _sample_ndvi(item, lat, lon)
    if ndvi_raw is not None:
        return _ndvi_to_stress(ndvi_raw)
 
    # ── Cloud-cover proxy ─────────────────────────────────────────────────────
    # rasterio unavailable → use cloud cover as a weak crop-risk signal.
    # High cloud ≈ waterlogging / humidity-driven disease pressure.
    # Caps at 0.50 so it doesn't dominate the score the way a real pixel read would.
    cloud_pct = item["properties"].get("eo:cloud_cover", 0)
    proxy = round(min(1.0, cloud_pct / 100.0) * 0.50, 3)
    logger.debug("NDVI cloud-proxy for (%.4f, %.4f): cloud=%.0f%% → stress=%.2f",
                 lat, lon, cloud_pct, proxy)
    return proxy
 
 
def _find_best_scene(lat: float, lon: float, timeout: float) -> Optional[dict]:
    """Query STAC for the most recent Sentinel-2 L2A scene with acceptable cloud cover."""
    now   = datetime.utcnow()
    start = now - timedelta(days=LOOKBACK_DAYS)
 
    payload = {
        "collections": [COLLECTION],
        "bbox": [
            lon - BBOX_HALF_DEG, lat - BBOX_HALF_DEG,
            lon + BBOX_HALF_DEG, lat + BBOX_HALF_DEG,
        ],
        "datetime": (
            f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/"
            f"{now.strftime('%Y-%m-%dT%H:%M:%SZ')}"
        ),
        "query":   {"eo:cloud_cover": {"lte": MAX_CLOUD_PCT}},
        "sortby":  [{"field": "properties.datetime", "direction": "desc"}],
        "limit":   1,
    }
 
    resp = requests.post(STAC_SEARCH, json=payload, timeout=timeout)
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        logger.info(
            "No Sentinel-2 scene (cloud<=%d%%) in last %dd for (%.4f, %.4f)",
            MAX_CLOUD_PCT, LOOKBACK_DAYS, lat, lon,
        )
        return None
    return features[0]
 
 
def _sample_ndvi(item: dict, lat: float, lon: float) -> Optional[float]:
    """
    Read a single pixel from Sentinel-2 B04 (Red) and B08 (NIR) COG bands
    using rasterio windowed reads.  Only the tile containing the target point
    is fetched — typically a few hundred KB, not the full 1 GB scene.
 
    Returns raw NDVI float, or None if rasterio / pyproj are not installed.
    """
    try:
        import rasterio                                       # type: ignore
        from rasterio.windows import from_bounds as win_from_bounds  # type: ignore
        from pyproj import Transformer                         # type: ignore
    except ImportError:
        logger.debug("rasterio/pyproj absent — using cloud-cover proxy instead")
        return None
 
    assets   = item.get("assets", {})
    b04_href = _asset_href(assets, ["red",  "B04", "b04"])
    b08_href = _asset_href(assets, ["nir",  "B08", "b08"])
    if not b04_href or not b08_href:
        logger.warning("Missing Red/NIR assets in scene %s", item.get("id"))
        return None
 
    gdal_env = dict(
        GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
        GDAL_HTTP_MULTIPLEX="YES",
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff",
    )
 
    def read_pixel(href: str) -> float:
        url = href if href.startswith(("http", "s3")) else href
        vsi = f"/vsicurl/{url}" if not url.startswith("/vsicurl") else url
        with rasterio.Env(**gdal_env):
            with rasterio.open(vsi) as src:
                tfm = Transformer.from_crs("EPSG:4326", src.crs.to_epsg(), always_xy=True)
                x, y = tfm.transform(lon, lat)
                half = src.res[0] / 2
                win  = win_from_bounds(x - half, y - half, x + half, y + half, src.transform)
                data = src.read(1, window=win)
                return float(data.mean())
 
    red = read_pixel(b04_href)
    nir = read_pixel(b08_href)
 
    denom = nir + red
    return round((nir - red) / denom, 4) if denom != 0 else 0.0
 
 
def _asset_href(assets: dict, keys: list[str]) -> Optional[str]:
    for k in keys:
        a = assets.get(k)
        if a:
            return a.get("href") or (a.get("alternate") or {}).get("s3", {}).get("href")
    return None
 
 
def _ndvi_to_stress(ndvi: float) -> float:
    """
    Piecewise-linear mapping from raw NDVI to a 0-1 urgency/stress score.
    NDVI ≥ NDVI_HEALTHY  → 0.0 (healthy, no urgency)
    NDVI ≤ NDVI_STRESSED → 1.0 (critical stress)
    """
    if ndvi >= NDVI_HEALTHY:
        return 0.0
    if ndvi <= NDVI_STRESSED:
        return 1.0
    span = NDVI_HEALTHY - NDVI_STRESSED
    return round((NDVI_HEALTHY - ndvi) / span, 3)
 
 
# ── cache helpers ─────────────────────────────────────────────────────────────
 
def _get_cached(key: str) -> Optional[float]:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        if time.time() - entry["ts"] > CACHE_TTL_H * 3600:
            del _CACHE[key]
            return None
        return entry["value"]
 
 
def _set_cached(key: str, value: float) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = {"value": value, "ts": time.time()}