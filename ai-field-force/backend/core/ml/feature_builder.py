from core.deterministic.signal_normalizer import (
    normalize_days_since_visit,
    normalize_pest_severity,
    normalize_inventory,
    normalize_revenue_potential,
)
 
 
def build_feature_vector(entity: dict, signals: dict) -> dict:
    payload = signals.get(entity["id"], {})
 
    return {
        # ── existing 8 signals ────────────────────────────────────────────────
        "pest_alert_severity":      normalize_pest_severity(
                                        payload.get("pest_alert_severity", "none")
                                    ),
        "inventory_shortage_level": normalize_inventory(
                                        payload.get("inventory_shortage_level", 0.5)
                                    ),
        "days_since_last_visit":    normalize_days_since_visit(
                                        payload.get("days_since_last_visit", 0)
                                    ),
        "weather_risk_score":       float(payload.get("weather_risk_score", 0.0)),
        "complaint_open":           1.0 if payload.get("complaint_open") else 0.0,
        "crop_stage_sensitivity":   float(payload.get("crop_stage_sensitivity", 0.0)),
        "revenue_potential":        normalize_revenue_potential(
                                        payload.get("revenue_potential", 0.0),
                                        payload.get("max_ltv", 1.0)
                                    ),
        "competitor_activity":      1.0 if payload.get("competitor_activity") else 0.0,
 
        # ── 9th signal: Sentinel-2 NDVI crop-health ───────────────────────────
        # Already normalised 0-1 by core/integrations/ndvi.py; 0 = healthy,
        # 1 = severe stress.  Stored in payload as "ndvi_stress" by the refresh task.
        # Default 0.0 (assume healthy) when the refresh task hasn't run yet.
        "ndvi_stress":              float(payload.get("ndvi_stress", 0.0)),
    }