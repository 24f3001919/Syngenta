"""
Tests for rep-observed competitor activity from outcome form.

When a rep submits an outcome with competitor_seen=True, the grower's signal
payload should be updated to mark competitor_activity=True with source
'rep_observed'. When False, the signal should be untouched.
"""
import uuid
import pytest

from models.db.farmers import FarmerRetailer
from models.db.signal import Signal


# ─── Fixture: a grower with a known composite signal ──────────────────────────

@pytest.fixture(scope="function")
def test_grower_with_signal(test_db, seeded_rep):
    """Grower + composite signal with competitor_activity initially False."""
    grower = FarmerRetailer(
        id="GRW_COMP_TEST",
        name="Competitor Test Grower",
        type="farmer",
        region="Test Region",
        rep_id="REP_TEST",
        lat=28.0,
        lng=73.0,
    )
    test_db.add(grower)

    sig = Signal(
        entity_id=grower.id,
        signal_type="composite",
        payload={
            "pest_alert_severity":      "low",
            "weather_risk_score":       0.2,
            "competitor_activity":      False,
            "ndvi_stress":              0.3,
            "inventory_shortage_level": 0.1,
        },
    )
    test_db.add(sig)
    test_db.commit()
    return grower


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_outcome_with_competitor_seen_updates_signal(client, auth_headers, test_grower_with_signal, test_db):
    """Submitting outcome with competitor_seen=True writes to signal payload."""
    body = {
        "entity_id": test_grower_with_signal.id,
        "outcome_rating": 4,
        "outcome_type": "follow_up_needed",
        "actions_taken": ["Demonstrated product"],
        "actions_accepted": [],
        "notes": "Saw Bayer product at the retailer",
        "competitor_seen": True,
    }
    res = client.post("/outcomes/record", json=body, headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "created"

    # Reload the signal from DB
    test_db.expire_all()
    sig = (
        test_db.query(Signal)
        .filter(Signal.entity_id == test_grower_with_signal.id)
        .order_by(Signal.created_at.desc())
        .first()
    )
    assert sig is not None
    assert sig.payload["competitor_activity"] is True
    assert sig.payload["competitor_source"] == "rep_observed"


def test_outcome_without_competitor_seen_does_not_mutate_signal(client, auth_headers, test_grower_with_signal, test_db):
    """Submitting outcome with competitor_seen=False leaves signal untouched."""
    body = {
        "entity_id": test_grower_with_signal.id,
        "outcome_rating": 4,
        "outcome_type": "follow_up_needed",
        "actions_taken": [],
        "actions_accepted": [],
        "notes": "Normal visit, no competitor seen",
        "competitor_seen": False,
    }
    res = client.post("/outcomes/record", json=body, headers=auth_headers)
    assert res.status_code == 200

    test_db.expire_all()
    sig = (
        test_db.query(Signal)
        .filter(Signal.entity_id == test_grower_with_signal.id)
        .order_by(Signal.created_at.desc())
        .first()
    )
    # competitor_activity stays at the initial seeded value (False)
    assert sig.payload["competitor_activity"] is False
    # No competitor_source key — helper didn't run
    assert sig.payload.get("competitor_source") is None


def test_outcome_competitor_seen_defaults_to_false(client, auth_headers, test_grower_with_signal, test_db):
    """Backward compat: clients that don't send competitor_seen default to False."""
    body = {
        "entity_id": test_grower_with_signal.id,
        "outcome_rating": 3,
        "outcome_type": "no_interest",
        "actions_taken": [],
        "actions_accepted": [],
        # NOTE: deliberately omitting competitor_seen
    }
    res = client.post("/outcomes/record", json=body, headers=auth_headers)
    assert res.status_code == 200

    test_db.expire_all()
    sig = (
        test_db.query(Signal)
        .filter(Signal.entity_id == test_grower_with_signal.id)
        .order_by(Signal.created_at.desc())
        .first()
    )
    # Same as the False test — signal not mutated
    assert sig.payload["competitor_activity"] is False
    assert sig.payload.get("competitor_source") is None