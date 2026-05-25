"""
Tests for the /signals/* endpoints (anomalies, NDVI, pest).

These touch live external APIs (Element84 STAC for NDVI, ICAR for pest).
We test the API CONTRACT — status codes, payload shape, graceful fallback —
not the specific external data, since gov sites are unreliable.

Covers:
  - /signals/anomalies requires auth (401 without token)
  - /signals/anomalies returns list with auth
  - /signals/pest/{id} ALWAYS returns 200 with structured data (live or baseline)
  - /signals/ndvi/{id} returns 200 with scene metadata fields
"""
import uuid
import pytest

from models.db.farmers import FarmerRetailer


# ─── Helper: create a test grower with valid lat/lon + region ─────────────────

@pytest.fixture(scope="function")
def test_grower(test_db, seeded_rep):
    """Create one grower with valid coords for signal endpoint tests."""
    grower = FarmerRetailer(
        id="GRW_TEST_001",
        name="Test Grower Bikaner",
        type="farmer",
        region="Bikaner, Rajasthan",
        rep_id="REP_TEST",
        lat=28.0229,
        lng=73.3119,
    )
    test_db.add(grower)
    test_db.commit()
    return grower


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_anomalies_requires_auth(client):
    """Unauthenticated request returns 401."""
    res = client.get("/signals/anomalies")
    assert res.status_code == 401


def test_anomalies_returns_structured_response_with_auth(client, auth_headers, test_grower):
    """Authenticated request returns 200 with {rep_id, results, total_flagged} envelope."""
    res = client.get("/signals/anomalies", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, dict)
    assert body["rep_id"] == "REP_TEST"
    assert isinstance(body["results"], list)
    assert "total_flagged" in body
    assert isinstance(body["total_flagged"], int)


def test_pest_endpoint_always_returns_200_with_baseline_fallback(client, auth_headers, test_grower):
    """Pest endpoint never 503s — falls back to deterministic baseline when
    live ICAR/IMD sources are unreachable (which they often are)."""
    res = client.get(f"/signals/pest/{test_grower.id}", headers=auth_headers)
    assert res.status_code == 200, res.text
    body = res.json()

    # Required fields regardless of data source
    assert body["entity_id"] == test_grower.id
    assert body["region"] == "Bikaner, Rajasthan"
    assert body["severity"] in ("high", "medium", "low", "none")
    assert body["district"] == "bikaner"
    assert "source" in body
    assert "is_live" in body  # True for live data, False for baseline

    # If baseline, lineage should be marked
    if not body["is_live"]:
        assert body["source"] == "deterministic_baseline"


def test_pest_endpoint_404_for_nonexistent_grower(client, auth_headers, test_db):
    """Bad entity_id returns 404, not 500."""
    res = client.get("/signals/pest/GRW_DOES_NOT_EXIST", headers=auth_headers)
    assert res.status_code == 404


def test_ndvi_endpoint_returns_scene_metadata(client, auth_headers, test_grower):
    """NDVI endpoint hits Element84 STAC. Either succeeds (200 with scene data)
    or fails (503). Either way the contract is enforced."""
    res = client.get(f"/signals/ndvi/{test_grower.id}", headers=auth_headers)
    # Accept 200 (live data) or 503 (STAC unavailable)
    assert res.status_code in (200, 503), res.text

    if res.status_code == 200:
        body = res.json()
        assert body["entity_id"] == test_grower.id
        # Scene metadata fields present (values may be null)
        assert "scene_date" in body
        assert "cloud_cover_pct" in body
        assert "source" in body