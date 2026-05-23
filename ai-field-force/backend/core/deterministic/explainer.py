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


# Semantic family map: reasons in the same family describe the same situation
# at different severity. We keep at most one per family (the strongest).
# Maps each leaf reason → its family.
REASON_FAMILY = {
    # Pest family
    "override.pest_outbreak_region": "pest",
    "pest_critical":                 "pest",
    "pest_alert":                    "pest",
    # Visit family
    "override.visit_overdue_30":     "visit",
    "visit_overdue_21":              "visit",
    "visit_due_14":                  "visit",
    # Complaint family
    "override.complaint_immediate":  "complaint",
    "complaint_open":                "complaint",
    # Inventory family
    "inventory_critical":            "inventory",
    "inventory_low":                 "inventory",
}

# Within each family, lower index = higher priority (kept; rest dropped).
FAMILY_PRIORITY = {
    "pest":      ["override.pest_outbreak_region", "pest_critical", "pest_alert"],
    "visit":     ["override.visit_overdue_30", "visit_overdue_21", "visit_due_14"],
    "complaint": ["override.complaint_immediate", "complaint_open"],
    "inventory": ["inventory_critical", "inventory_low"],
}


def _dedupe_by_family(reasons: list[str]) -> list[str]:
    """Keep at most one reason per semantic family. Preserves input order otherwise."""
    seen_families: dict[str, str] = {}  # family -> chosen code
    standalone: list[str] = []

    for r in reasons:
        family = REASON_FAMILY.get(r)
        if family is None:
            # Not in any family — keep as-is
            standalone.append(r)
            continue
        current = seen_families.get(family)
        if current is None:
            seen_families[family] = r
        else:
            # Compare priorities; keep the stronger
            priorities = FAMILY_PRIORITY[family]
            current_idx = priorities.index(current) if current in priorities else 999
            new_idx     = priorities.index(r)       if r       in priorities else 999
            if new_idx < current_idx:
                seen_families[family] = r

    # Rebuild preserving original order
    chosen = set(seen_families.values()) | set(standalone)
    return [r for r in reasons if r in chosen]


def extract_top_reasons(
    features: dict,
    weights: dict,
    overrides: list[str]
) -> list[str]:
    """Returns up to 3 stable reason codes, semantically deduped.
    If override.pest_outbreak_region AND reason.pest_critical both fire, only the
    stronger (override) is kept."""
    raw = list(overrides)
    contributions = {
        signal: features.get(signal, 0.0) * weight
        for signal, weight in weights.items()
    }
    top_signals = sorted(contributions, key=contributions.get, reverse=True)
    for signal in top_signals:
        code = resolve_reason_code(signal, features.get(signal, 0.0))
        if code:
            raw.append(code)

    # Dedupe by semantic family, then trim to 3
    deduped = _dedupe_by_family(raw)
    return deduped[:3]


# Backwards-compat wrapper
resolve_reason_template = resolve_reason_code