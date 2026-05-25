"""
Tests for deterministic NDVI seeding.

The _seed_ndvi_stress helper generates a per-grower stress score that is:
  1. Deterministic — same entity_id + district + pest_severity always returns same value
  2. Bounded — always in [0.0, 0.9] (clamped)
  3. Sensitive to pest pressure — high pest severity nudges stress UP, none nudges DOWN

These properties matter because they keep priority cards stable across Render
ephemeral-disk reseeds and across local dev restarts.
"""
from db.seed_data import _seed_ndvi_stress


def test_ndvi_stress_is_deterministic():
    """Same input → same output. No randomness."""
    a = _seed_ndvi_stress("GRW_00311", "Bikaner", "medium")
    b = _seed_ndvi_stress("GRW_00311", "Bikaner", "medium")
    c = _seed_ndvi_stress("GRW_00311", "Bikaner", "medium")
    assert a == b == c, f"Non-deterministic: {a}, {b}, {c}"


def test_ndvi_stress_in_valid_range():
    """Output must always be between 0.0 and 0.9 (inclusive)."""
    for entity_id in ("GRW_00001", "GRW_99999", "GRW_TEST", "GRW_XYZ"):
        for district in ("Bikaner", "Pune", "Meerut"):
            for severity in ("high", "medium", "low", "none"):
                v = _seed_ndvi_stress(entity_id, district, severity)
                assert 0.0 <= v <= 0.9, \
                    f"NDVI stress out of range for ({entity_id}, {district}, {severity}): {v}"


def test_ndvi_stress_responds_to_pest_pressure():
    """High pest pressure should nudge NDVI stress UPWARD compared to none."""
    high = _seed_ndvi_stress("GRW_00311", "Bikaner", "high")
    none = _seed_ndvi_stress("GRW_00311", "Bikaner", "none")
    assert high > none, \
        f"High pest pressure should raise NDVI stress: high={high}, none={none}"


def test_ndvi_stress_different_growers_different_values():
    """Different entity IDs in same district should produce different stress values
    (sanity check — confirms the hash is actually varying per grower)."""
    values = {
        _seed_ndvi_stress(f"GRW_{i:05d}", "Bikaner", "medium")
        for i in range(20)
    }
    # 20 growers should produce at least 5 unique values (allowing some collisions)
    assert len(values) >= 5, \
        f"Hash too lossy — only {len(values)} unique values across 20 growers"