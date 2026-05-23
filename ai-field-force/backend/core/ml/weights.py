SIGNAL_WEIGHTS = {
    "pest_alert_severity":      0.23,   # was 0.25 — live ICAR district advisory
    "inventory_shortage_level": 0.19,   # was 0.20
    "days_since_last_visit":    0.17,   # was 0.18
    "weather_risk_score":       0.11,   # was 0.12 — Open-Meteo 7-day forecast
    "complaint_open":           0.09,   # was 0.10
    "ndvi_stress":              0.07,   # NEW  — Sentinel-2 L2A crop-health
    "crop_stage_sensitivity":   0.07,   # was 0.08
    "revenue_potential":        0.05,   # unchanged
    "competitor_activity":      0.02,   # unchanged
}
 
assert round(sum(SIGNAL_WEIGHTS.values()), 10) == 1.0