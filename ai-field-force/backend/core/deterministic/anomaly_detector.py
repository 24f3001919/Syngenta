ANOMALY_RULES = [
    {
        "name":     "stock_critically_low",
        "check":    lambda e: e.get("inventory_pct", 1.0) < 0.10,
        "severity": "critical",
        "message":  "anomaly.stock_critically_low"
    },
    {
        "name":     "visit_gap_exceeded",
        "check":    lambda e: e.get("days_since_last_visit", 0) > 21,
        "severity": "high",
        "message":  "anomaly.visit_gap_exceeded"
    },
    {
        "name":     "competitor_spotted",
        "check":    lambda e: e.get("competitor_activity") == True,
        "severity": "medium",
        "message":  "anomaly.competitor_spotted"
    },
    {
        "name":     "complaint_unresolved",
        "check":    lambda e: e.get("complaint_open") == True,
        "severity": "high",
        "message":  "anomaly.complaint_unresolved"
    },
]


def run_anomaly_checks(entity: dict) -> list[dict]:
    triggered = []
    for rule in ANOMALY_RULES:
        try:
            if rule["check"](entity):
                triggered.append({
                    "type":     rule["name"],
                    "severity": rule["severity"],
                    "message":  rule["message"]   # now a translation key
                })
        except Exception:
            continue
    return triggered