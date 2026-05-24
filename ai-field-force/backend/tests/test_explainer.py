"""
Tests for the deterministic reason-code resolver and family-based dedup.

These are pure-function tests — no DB, no FastAPI. Run fast.

Covers:
  - NDVI severe stress emits ndvi_high_stress reason (fast-path)
  - Pest override beats pest_critical reason (family dedup keeps stronger)
  - Visit family: override.visit_overdue_30 beats visit_due_14
  - Top reasons limited to 3 max
"""
from core.deterministic.explainer import (
    extract_top_reasons,
    resolve_reason_code,
    _dedupe_by_family,
)
from core.ml.weights import SIGNAL_WEIGHTS


def test_ndvi_high_stress_emits_reason_via_fast_path():
    """NDVI >= 0.6 surfaces ndvi_high_stress even with low weight (0.07)."""
    features = {
        "pest_alert_severity":      0.0,
        "inventory_shortage_level": 0.0,
        "days_since_last_visit":    0.0,
        "weather_risk_score":       0.0,
        "complaint_open":           0.0,
        "crop_stage_sensitivity":   0.0,
        "revenue_potential":        0.0,
        "competitor_activity":      0.0,
        "ndvi_stress":              0.75,  # severe
    }
    reasons = extract_top_reasons(features, SIGNAL_WEIGHTS, overrides=[])
    assert "ndvi_high_stress" in reasons, \
        f"Expected ndvi_high_stress in reasons, got {reasons}"


def test_override_pest_beats_reason_pest_in_family_dedup():
    """When both override.pest_outbreak_region AND pest_critical fire,
    only the override survives (it's stronger in the pest family)."""
    raw = ["override.pest_outbreak_region", "pest_critical", "pest_alert"]
    deduped = _dedupe_by_family(raw)
    assert "override.pest_outbreak_region" in deduped
    assert "pest_critical" not in deduped
    assert "pest_alert" not in deduped


def test_visit_family_keeps_most_severe():
    """visit family: override.visit_overdue_30 > visit_overdue_21 > visit_due_14."""
    raw = ["visit_due_14", "override.visit_overdue_30", "visit_overdue_21"]
    deduped = _dedupe_by_family(raw)
    assert "override.visit_overdue_30" in deduped
    assert "visit_overdue_21" not in deduped
    assert "visit_due_14" not in deduped


def test_top_reasons_limited_to_three():
    """No matter how many signals fire, output is capped at 3 reasons."""
    features = {
        "pest_alert_severity":      0.9,   # → pest_critical
        "inventory_shortage_level": 0.95,  # → inventory_critical
        "days_since_last_visit":    0.85,  # → visit_overdue_21
        "weather_risk_score":       0.8,
        "complaint_open":           1.0,   # → complaint_open
        "crop_stage_sensitivity":   0.8,
        "revenue_potential":        0.7,
        "competitor_activity":      1.0,
        "ndvi_stress":              0.8,   # → ndvi_high_stress (fast-path)
    }
    reasons = extract_top_reasons(features, SIGNAL_WEIGHTS, overrides=[])
    assert len(reasons) <= 3, f"Should cap at 3, got {len(reasons)}: {reasons}"


def test_resolve_reason_code_returns_none_for_low_signals():
    """Sub-threshold signal values return None (no reason emitted)."""
    assert resolve_reason_code("pest_alert_severity", 0.1) is None
    assert resolve_reason_code("days_since_last_visit", 0.3) is None
    assert resolve_reason_code("ndvi_stress", 0.2) is None
    # Unknown signal → None
    assert resolve_reason_code("unknown_signal", 0.99) is None