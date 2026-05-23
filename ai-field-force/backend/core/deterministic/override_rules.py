def apply_overrides(entity: dict, vps: float) -> tuple[float, list[str]]:
    """Apply business-rule overrides. Returns adjusted VPS and a list of stable reason codes.
    Frontend translates the codes via LangContext."""
    overrides = []
    if entity.get("complaint_open"):
        vps = max(vps, 90.0)
        overrides.append("override.complaint_immediate")
    if entity.get("pest_alert_severity") == "high":
        vps = max(vps, 85.0)
        overrides.append("override.pest_outbreak_region")
    if entity.get("days_since_last_visit", 0) >= 30:
        vps = max(vps, 75.0)
        overrides.append("override.visit_overdue_30")
    return vps, overrides