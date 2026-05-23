from __future__ import annotations
 
import logging
import threading
from datetime import datetime
from typing import Optional
 
from sqlalchemy.orm.attributes import flag_modified
 
from db.session                  import SessionLocal
from models.db.farmers           import FarmerRetailer
from models.db.signal            import Signal
from core.integrations.ndvi      import fetch_ndvi_risk_score
from core.integrations.icar_pest import fetch_pest_severity
 
logger = logging.getLogger(__name__)
 
REFRESH_INTERVAL_H  = 6          # hours between scheduled refreshes
_stop_event         = threading.Event()
_refresh_thread: Optional[threading.Thread] = None
 
 
# ═══════════════════════════════ public API ═══════════════════════════════════
 
def run_once() -> dict:
    """
    Refresh NDVI + pest signals for all entities.  Blocking — run via
    background thread or a FastAPI BackgroundTask.
 
    Returns a summary dict suitable for an API response.
    """
    db = SessionLocal()
    try:
        return _do_refresh(db)
    finally:
        db.close()
 
 
def start_background_scheduler() -> None:
    """
    Spawn a daemon thread that calls run_once() immediately on startup and
    then every REFRESH_INTERVAL_H hours.
 
    Call this from main.py's @app.on_event("startup").
    """
    global _refresh_thread
    _stop_event.clear()
 
    def _loop() -> None:
        logger.info(
            "Signal refresh scheduler started (interval=%dh, sources=Sentinel-2+ICAR)",
            REFRESH_INTERVAL_H,
        )
        _safe_run()
        while not _stop_event.wait(timeout=REFRESH_INTERVAL_H * 3600):
            _safe_run()
 
    _refresh_thread = threading.Thread(
        target=_loop, name="signal-refresh", daemon=True
    )
    _refresh_thread.start()
 
 
def stop_background_scheduler() -> None:
    """Call from @app.on_event("shutdown") if graceful drain matters."""
    _stop_event.set()
 
 
# ═══════════════════════════════ internal ═════════════════════════════════════
 
def _safe_run() -> None:
    try:
        result = run_once()
        logger.info(
            "Signal refresh done: updated=%d  skipped=%d  errors=%d",
            result["updated"], result["skipped"], result["errors"],
        )
    except Exception as exc:
        logger.error("Signal refresh run failed: %s", exc, exc_info=True)
 
 
def _do_refresh(db) -> dict:
    entities = db.query(FarmerRetailer).all()
    updated = skipped = errors = 0
 
    for entity in entities:
        try:
            changed = _refresh_entity(db, entity)
            if changed:
                updated += 1
            else:
                skipped += 1
        except Exception as exc:
            logger.warning("Entity %s refresh failed: %s", entity.id, exc)
            errors += 1
 
    db.commit()
    return {
        "refreshed_at": datetime.utcnow().isoformat(),
        "total":        len(entities),
        "updated":      updated,
        "skipped":      skipped,
        "errors":       errors,
    }
 
 
def _refresh_entity(db, entity: FarmerRetailer) -> bool:
    """
    Fetch fresh NDVI and pest data for one entity; update its Signal row.
    Returns True if the payload was actually changed.
    """
    if entity.lat is None or entity.lng is None:
        return False
 
    # ── fetch from external sources ──────────────────────────────────────────
    ndvi_stress   = fetch_ndvi_risk_score(entity.lat, entity.lng)
    pest_severity = fetch_pest_severity(entity.region or "")
 
    # Both unavailable — preserve whatever is already stored.
    if ndvi_stress is None and pest_severity is None:
        return False
 
    # ── load or create the Signal row ────────────────────────────────────────
    signal = (
        db.query(Signal)
        .filter(Signal.entity_id == entity.id)
        .first()
    )
    if signal is None:
        signal = Signal(entity_id=entity.id, payload={})
        db.add(signal)
 
    payload = dict(signal.payload or {})
    changed = False
 
    # ── NDVI ─────────────────────────────────────────────────────────────────
    if ndvi_stress is not None:
        old = payload.get("ndvi_stress")
        if old != ndvi_stress:
            payload["ndvi_stress"]       = ndvi_stress
            payload["ndvi_refreshed_at"] = datetime.utcnow().isoformat()
            payload["ndvi_source"]       = "sentinel2_element84"
            changed = True
            logger.debug(
                "Entity %-12s  NDVI stress: %s → %.3f",
                entity.id, f"{old:.3f}" if old is not None else "—", ndvi_stress,
            )
 
    # ── pest severity (ICAR) ─────────────────────────────────────────────────
    if pest_severity is not None:
        old = payload.get("pest_alert_severity")
        if old != pest_severity:
            payload["pest_alert_severity"] = pest_severity
            payload["pest_source"]          = "icar_ncipm"
            payload["pest_refreshed_at"]    = datetime.utcnow().isoformat()
            changed = True
            logger.debug(
                "Entity %-12s  pest severity: %s → %s",
                entity.id, old or "—", pest_severity,
            )
 
    if changed:
        signal.payload = payload
        # Explicitly mark the JSON column dirty — SQLAlchemy may miss in-place mutations.
        flag_modified(signal, "payload")
 
    return changed