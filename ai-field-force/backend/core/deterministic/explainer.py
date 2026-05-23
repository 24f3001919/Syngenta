def resolve_reason_code(signal: str, value) -> str | None:
    """Return a stable reason code (not display text). Frontend translates."""
    if signal == "pest_alert_severity":
        if value >= 0.65:
            return "pest_critical"
        if value >= 0.3:
            return "pest_alert"
    elif signal == "inventory_shortage_level":
        if value >= 0.8:
            return "inventory_critical"
        if value >= 0.5:
            return "inventory_low"
    elif signal == "days_since_last_visit":
        if value >= 1.0:
            return "visit_overdue_21"
        if value >= 0.67:
            return "visit_due_14"
    elif signal == "complaint_open":
        if value == 1.0:
            return "complaint_open"
    elif signal == "competitor_activity":
        if value == 1.0:
            return "competitor_spotted"
    elif signal == "weather_risk_score":
        if value >= 0.7:
            return "weather_high_risk"
    elif signal == "crop_stage_sensitivity":
        if value >= 0.7:
            return "crop_stage_critical"
    return None


def extract_top_reasons(
    features: dict,
    weights: dict,
    overrides: list[str]
) -> list[str]:
    """Returns up to 3 stable reason codes. Frontend translates via LangContext."""
    reasons = list(overrides)
    contributions = {
        signal: features.get(signal, 0.0) * weight
        for signal, weight in weights.items()
    }
    top_signals = sorted(contributions, key=contributions.get, reverse=True)
    for signal in top_signals:
        if len(reasons) >= 3:
            break
        code = resolve_reason_code(signal, features.get(signal, 0.0))
        if code:
            reasons.append(code)
    return reasons


# Backwards-compat wrapper, in case anything still imports the old name
resolve_reason_template = resolve_reason_code