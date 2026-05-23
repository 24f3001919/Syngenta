from __future__ import annotations
 
import logging
import re
import threading
import time
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree as ET
 
import requests
 
logger = logging.getLogger(__name__)
 
# ── source URLs ───────────────────────────────────────────────────────────────
NCIPM_ADVISORY = "http://www.ncipm.org.in/ncipmweb/PestAdvisoriesManagement"
NCIPM_HOME     = "http://www.ncipm.org.in/"
IMD_AAS_DIST   = "https://aas.imd.gov.in/district_level_aas.php"
ICAR_RSS       = "https://www.icar.org.in/rss.xml"
PPQS_PEST      = "https://ppqs.gov.in/pest-surveillance"
 
REQUEST_TIMEOUT = 8.0        # seconds; government sites can be slow
CACHE_TTL_H     = 6          # hours between refreshes
 
# ── district normalization ────────────────────────────────────────────────────
# Region strings from our DB: "Bikaner, Rajasthan", "Sikar, Rajasthan", etc.
# Government sources use inconsistent spellings — we normalize both sides.
DISTRICT_ALIASES: dict[str, list[str]] = {
    "bikaner":      ["bikaner"],
    "churu":        ["churu"],
    "ganganagar":   ["sri ganganagar", "sriganganagar", "ganganagar"],
    "hanumangarh":  ["hanumangarh"],
    "jaipur":       ["jaipur"],
    "jodhpur":      ["jodhpur"],
    "barmer":       ["barmer", "balotra"],
    "nagaur":       ["nagaur"],
    "sikar":        ["sikar"],
    "ajmer":        ["ajmer"],
    "mehsana":      ["mahesana", "mehsana"],
    "meerut":       ["meerut", "meerath"],
    "pune":         ["pune", "poona"],
    "nashik":       ["nashik", "nasik"],
}
 
# Severity keywords — checked high→medium→low→none so a "severe" text
# doesn't accidentally get classified as "low" via a substring match.
_SEVERITY_MAP: list[tuple[str, list[str]]] = [
    ("high",   [
        "heavy infestation", "severe", "critical", "outbreak",
        "high incidence", "high severity", "बहुत अधिक", "अत्यधिक",
        "alert", "widespread",
    ]),
    ("medium", [
        "moderate", "medium incidence", "moderate infestation",
        "मध्यम", "sporadic",
    ]),
    ("low",    [
        "low incidence", "light infestation", "light", "mild",
        "कम", "trace",
    ]),
    ("none",   [
        "nil", "no incidence", "absent", "no pest", "none",
        "not observed",
    ]),
]
 
# district_key → {"severity", "source", "fetched_at", "_ts"}
_CACHE:      dict[str, dict] = {}
_CACHE_LOCK: threading.Lock  = threading.Lock()
 
 
# ═══════════════════════════════ public API ═══════════════════════════════════
 
def fetch_pest_severity(region: str, timeout: float = REQUEST_TIMEOUT) -> Optional[str]:
    """
    Given a region string (e.g. "Bikaner, Rajasthan") return the current
    advisory severity for that district.
 
    Returns None if every source is unavailable — the caller should retain
    whatever value was previously stored in Signal.payload.
    """
    district_key = _extract_district_key(region)
    if not district_key:
        logger.debug("Could not extract district key from region: %r", region)
        return None
 
    cached = _get_cached(district_key)
    if cached is not None:
        return cached["severity"]
 
    severity = (
        _from_ncipm(district_key, timeout)
        or _from_imd_aas(district_key, timeout)
        or _from_icar_rss(district_key, timeout)
        or _from_ppqs(district_key, timeout)
    )
 
    if severity:
        _set_cached(district_key, {
            "severity":   severity,
            "district":   district_key,
            "fetched_at": datetime.utcnow().isoformat(),
        })
        logger.info("Pest severity [%s] → %s", district_key, severity)
    else:
        logger.info("No pest advisory found for district: %s", district_key)
 
    return severity
 
 
def fetch_pest_detail(region: str) -> Optional[dict]:
    """Extended response for API transparency — includes source provenance."""
    district_key = _extract_district_key(region)
    if not district_key:
        return None
 
    fetch_pest_severity(region)           # populate cache if empty
    cached = _get_cached(district_key)
    if cached:
        return {**cached, "region": region}
    return None
 
 
# ═══════════════════════════════ source fetchers ═══════════════════════════════
 
def _from_ncipm(district_key: str, timeout: float) -> Optional[str]:
    """
    ICAR-NCIPM weekly crop-pest scenario report.
    The portal publishes HTML tables with district × crop × pest × incidence.
    """
    for url in [NCIPM_ADVISORY, NCIPM_HOME]:
        try:
            resp = requests.get(url, timeout=timeout, headers=_ua())
            resp.raise_for_status()
            result = _parse_html(resp.text, district_key, source="ncipm")
            if result:
                return result
        except Exception as exc:
            logger.debug("NCIPM (%s) failed: %s", url, exc)
    return None
 
 
def _from_imd_aas(district_key: str, timeout: float) -> Optional[str]:
    """
    IMD Agromet Advisory Service — district-level crop & pest advisories
    updated twice weekly.  URL accepts a `state` query parameter.
    """
    state = _district_to_state(district_key)
    if not state:
        return None
    try:
        resp = requests.get(
            IMD_AAS_DIST,
            params={"state": state},
            timeout=timeout,
            headers=_ua(),
        )
        resp.raise_for_status()
        return _parse_html(resp.text, district_key, source="imd_aas")
    except Exception as exc:
        logger.debug("IMD AAS failed for state=%s: %s", state, exc)
        return None
 
 
def _from_icar_rss(district_key: str, timeout: float) -> Optional[str]:
    """
    ICAR general RSS — coarser signal but available when specialised portals
    are down.  We scan titles + descriptions for district mentions.
    """
    try:
        resp = requests.get(ICAR_RSS, timeout=timeout, headers=_ua())
        resp.raise_for_status()
        root    = ET.fromstring(resp.text)
        aliases = DISTRICT_ALIASES.get(district_key, [district_key])
        for item in root.findall(".//item"):
            text = (
                (item.findtext("title") or "") + " " +
                (item.findtext("description") or "")
            ).lower()
            if any(a in text for a in aliases):
                severity = _classify(text)
                if severity:
                    return severity
    except Exception as exc:
        logger.debug("ICAR RSS failed: %s", exc)
    return None
 
 
def _from_ppqs(district_key: str, timeout: float) -> Optional[str]:
    """DPPQS pest surveillance page — last resort."""
    try:
        resp = requests.get(PPQS_PEST, timeout=timeout, headers=_ua())
        resp.raise_for_status()
        return _parse_html(resp.text, district_key, source="ppqs")
    except Exception as exc:
        logger.debug("PPQS failed: %s", exc)
        return None
 
 
# ═══════════════════════════════ parsers ══════════════════════════════════════
 
def _parse_html(html: str, district_key: str, source: str) -> Optional[str]:
    """
    Try BeautifulSoup first (cleaner), fall back to regex strip.
    Scans table rows and text blocks for the district name, then
    classifies the surrounding text for severity.
    """
    aliases = DISTRICT_ALIASES.get(district_key, [district_key])
    try:
        from bs4 import BeautifulSoup                             # type: ignore
        soup = BeautifulSoup(html, "html.parser")
 
        # Strategy A: table rows
        for row in soup.find_all("tr"):
            cells = [td.get_text(separator=" ").lower()
                     for td in row.find_all(["td", "th"])]
            row_text = " ".join(cells)
            if any(a in row_text for a in aliases):
                sev = _classify(row_text)
                if sev:
                    logger.debug("[%s] Table row match for %s → %s", source, district_key, sev)
                    return sev
 
        # Strategy B: paragraph / list / div blocks
        for tag in soup.find_all(["p", "div", "li", "td", "article"]):
            text = tag.get_text(separator=" ").lower()
            if any(a in text for a in aliases):
                sev = _classify(text)
                if sev:
                    logger.debug("[%s] Text block match for %s → %s", source, district_key, sev)
                    return sev
    except ImportError:
        # BeautifulSoup not installed — regex fallback
        plain = re.sub(r"<[^>]+>", " ", html).lower()
        plain = re.sub(r"\s+", " ", plain)
        for alias in aliases:
            idx = plain.find(alias)
            if idx == -1:
                continue
            window = plain[max(0, idx - 150): idx + 400]
            sev = _classify(window)
            if sev:
                return sev
 
    return None
 
 
def _classify(text: str) -> Optional[str]:
    """Match the first (highest) severity level whose keywords appear in text."""
    t = text.lower()
    for severity, keywords in _SEVERITY_MAP:
        if any(kw in t for kw in keywords):
            return severity
    return None
 
 
# ═══════════════════════════════ helpers ══════════════════════════════════════
 
def _extract_district_key(region: str) -> Optional[str]:
    """
    "Bikaner, Rajasthan" → "bikaner"
    Tries exact match, then alias search, then returns the raw token.
    """
    if not region:
        return None
    raw = region.lower().split(",")[0].strip()
    if raw in DISTRICT_ALIASES:
        return raw
    for key, aliases in DISTRICT_ALIASES.items():
        if raw in aliases or any(a in raw for a in aliases):
            return key
    return raw   # unknown district — will likely produce no match but won't crash
 
 
def _district_to_state(district_key: str) -> Optional[str]:
    _MAP: dict[str, str] = {
        "bikaner":     "RAJASTHAN", "churu":      "RAJASTHAN",
        "ganganagar":  "RAJASTHAN", "hanumangarh":"RAJASTHAN",
        "jaipur":      "RAJASTHAN", "jodhpur":    "RAJASTHAN",
        "barmer":      "RAJASTHAN", "nagaur":     "RAJASTHAN",
        "sikar":       "RAJASTHAN", "ajmer":      "RAJASTHAN",
        "mehsana":     "GUJARAT",
        "meerut":      "UTTAR+PRADESH",
        "pune":        "MAHARASHTRA",
        "nashik":      "MAHARASHTRA",
    }
    return _MAP.get(district_key)
 
 
def _ua() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (compatible; FieldForceCopilot/1.0; "
            "+https://github.com/syngenta-hackathon)"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9,hi;q=0.5",
    }
 
 
# ── cache helpers ─────────────────────────────────────────────────────────────
 
def _get_cached(key: str) -> Optional[dict]:
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if not entry:
            return None
        if time.time() - entry["_ts"] > CACHE_TTL_H * 3600:
            del _CACHE[key]
            return None
        return {k: v for k, v in entry.items() if k != "_ts"}
 
 
def _set_cached(key: str, data: dict) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = {**data, "_ts": time.time()}