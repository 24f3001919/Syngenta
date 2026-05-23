# db/seed_data.py
import csv, json, random, uuid
from collections import defaultdict
from datetime import datetime, date
from db.session import SessionLocal, engine, Base
from models.db.farmers import FarmerRetailer
from models.db.signal import Signal
from models.db import outcome, visit
from core.integrations.weather import fetch_weather_summary

# Demo territory — 10 reps spread across 5 states.
# All 10 get seeded with growers + signals.
# A subset (see main.py) gets login accounts.
TARGET_REPS = [
    "REP_0338",  # Bikaner, Rajasthan  — primary demo rep
    "REP_0472",  # Sikar, Rajasthan
    "REP_0373",  # Sikar, Rajasthan
    "REP_0394",  # Mehsana, Gujarat
    "REP_0317",  # Jaipur, Rajasthan
    "REP_0426",  # Meerut, Uttar Pradesh
    "REP_0325",  # Muzaffarpur, Bihar
    "REP_0372",  # Kanpur Nagar, Uttar Pradesh
    "REP_0105",  # Lucknow, Uttar Pradesh
    "REP_0129",  # Meerut, Uttar Pradesh
]
TODAY = date(2026, 5, 15)

PEST_SEVERITY_MAP = {
    "wheat":    "medium",
    "mustard":  "high",
    "chickpea": "low",
    "barley":   "low",
    "lentil":   "none",
    "safflower":"medium",
}

CROP_SENSITIVITY_MAP = {
    "wheat":    0.7,
    "mustard":  0.85,
    "chickpea": 0.5,
    "barley":   0.45,
    "lentil":   0.4,
    "safflower":0.6,
}

# Rough lat/lon for each demo rep's district — used for real weather lookup
DISTRICT_COORDS = {
    "Bikaner":       (28.0229, 73.3119),
    "Sikar":         (27.6094, 75.1399),
    "Mehsana":       (23.5879, 72.3693),
    "Jaipur":        (26.9124, 75.7873),
    "Meerut":        (28.9845, 77.7064),
    "Muzaffarpur":   (26.1209, 85.3647),
    "Kanpur Nagar":  (26.4499, 80.3319),
    "Lucknow":       (26.8467, 80.9462),
}

WEATHER_FALLBACK_SCORE = 0.5

def _seed_ndvi_stress(entity_id: str, district: str, pest_severity: str) -> float:
    """
    Deterministic NDVI crop-stress seed value (0.0-0.9).
    Same input always produces same output (no randomness between reseeds).
    Higher pest severity in district → slightly higher stress.
    Used as a baseline until /signals/refresh fetches real Sentinel-2 data.
    """
    # Hash entity + district for stable per-grower value
    base = (sum(ord(c) for c in entity_id) + sum(ord(c) for c in district)) % 100
    stress = base / 100.0  # 0.0 to 0.99

    # Nudge based on pest pressure in the region
    if pest_severity == "high":
        stress = min(0.9, stress + 0.2)
    elif pest_severity == "medium":
        stress = min(0.8, stress + 0.1)
    elif pest_severity == "none":
        stress = max(0.05, stress - 0.2)

    return round(stress, 2)

def load_rep_data():
    """Returns {rep_id: {full row dict including parsed tehsil_list}}"""
    rep_info = {}
    with open("db/data/reps_territory.csv") as f:
        for r in csv.DictReader(f):
            r["tehsil_list_parsed"] = json.loads(r["tehsil_list"])
            rep_info[r["rep_id"]] = r
    return rep_info


def load_last_visits():
    last_visit = defaultdict(lambda: date(2025, 10, 1))
    with open("db/data/retailer_visit_log.csv") as f:
        for r in csv.DictReader(f):
            d = datetime.strptime(r["visit_date"], "%Y-%m-%d").date()
            if d > last_visit[r["rep_id"]]:
                last_visit[r["rep_id"]] = d
    return last_visit


def load_growers_for_rep(rep_tehsils):
    growers = []
    with open("db/data/growers.csv") as f:
        for r in csv.DictReader(f):
            if r["tehsil"] in rep_tehsils:
                growers.append(r)
    return growers


def load_tehsil_inventory(rep_tehsils):
    tehsil_retailers = defaultdict(list)
    with open("db/data/retailers.csv") as f:
        for r in csv.DictReader(f):
            if r["tehsil"] in rep_tehsils:
                tehsil_retailers[r["tehsil"]].append(r["retailer_id"])

    rep_retailer_set = set(
        rid for retailers in tehsil_retailers.values() for rid in retailers
    )

    retailer_inventory = defaultdict(list)
    with open("db/data/retailer_inventory_weekly.csv") as f:
        for r in csv.DictReader(f):
            if r["retailer_id"] in rep_retailer_set:
                retailer_inventory[r["retailer_id"]].append(r)

    if not retailer_inventory:
        return {}

    latest_week = max(
        r["week_end_date"]
        for rows in retailer_inventory.values()
        for r in rows
    )

    tehsil_inv = {}
    for tehsil, retailers in tehsil_retailers.items():
        all_qtys = []
        for rid in retailers:
            latest = [r for r in retailer_inventory[rid] if r["week_end_date"] == latest_week]
            for r in latest:
                all_qtys.append(int(r["sku_qty"]))
        if all_qtys:
            oos = sum(1 for q in all_qtys if q == 0)
            pct = round(1.0 - (oos / len(all_qtys)), 2)
            tehsil_inv[tehsil] = {
                "inventory_pct": pct,
                "inventory_shortage_level": round(1.0 - pct, 2)
            }

    return tehsil_inv


def fetch_weather_for_district(district: str):
    """One real weather call per district. Falls back gracefully."""
    coords = DISTRICT_COORDS.get(district)
    if not coords:
        return WEATHER_FALLBACK_SCORE, None

    lat, lon = coords
    summary = fetch_weather_summary(lat=lat, lon=lon)
    if summary is None:
        print(f"  ⚠ Open-Meteo unreachable for {district} — falling back to {WEATHER_FALLBACK_SCORE}")
        return WEATHER_FALLBACK_SCORE, None
    print(
        f"  ✓ Weather for {district}: score={summary['score']} "
        f"[precip={summary['components']['total_precipitation_mm_7d']}mm/7d, "
        f"hot_days≥38C={summary['components']['hot_days_above_38c_7d']}, "
        f"peak_wind={summary['components']['peak_wind_kmh_7d']}km/h]"
    )
    return summary["score"], summary


def seed_rep(db, rep_id, rep_row, last_visit_date, weather_cache):
    """Seed growers + signals for one rep. Returns (grower_count, district)."""
    rep_tehsils = set(rep_row["tehsil_list_parsed"])
    rep_district = rep_row["district"]
    rep_state    = rep_row["state"]
    days_since   = (TODAY - last_visit_date).days

    growers    = load_growers_for_rep(rep_tehsils)
    tehsil_inv = load_tehsil_inventory(rep_tehsils)

    if rep_district in weather_cache:
        weather_risk_score, weather_summary = weather_cache[rep_district]
    else:
        weather_risk_score, weather_summary = fetch_weather_for_district(rep_district)
        weather_cache[rep_district] = (weather_risk_score, weather_summary)

    entities = []
    for g in growers:
        entity = FarmerRetailer(
            id=g["grower_id"],
            name=f"Grower {g['grower_id'][-5:]}",
            type="farmer",
            lat=round(random.uniform(27.0, 29.5), 4),
            lng=round(random.uniform(72.0, 74.5), 4),
            region=f"{g['district']}, {g['state']}",
            rep_id=rep_id,
            last_visited_at=datetime.combine(last_visit_date, datetime.min.time()),
        )
        db.add(entity)
        entities.append((entity, g))

    db.commit()

    for entity, g in entities:
        try:
            cal   = json.loads(g["grower_crop_calendar"])
            crop  = cal.get("crop", "wheat")
            stages = [s["stage"] for s in cal.get("stages", [])]
            crop_stage = stages[-1] if stages else "unknown"
        except Exception:
            crop = "wheat"
            crop_stage = "unknown"

        pest_severity    = PEST_SEVERITY_MAP.get(crop, "low")
        crop_sensitivity = CROP_SENSITIVITY_MAP.get(crop, 0.5)

        inv = tehsil_inv.get(g["tehsil"], {})
        inventory_pct      = inv.get("inventory_pct", 0.5)
        inventory_shortage = inv.get("inventory_shortage_level", 0.5)

        farm_size = float(g.get("grower_farm_size") or 1.0)
        revenue_potential = min(100000.0, farm_size * 12000)

        product_scanned    = g.get("product_scan", "false").lower() == "true"
        campaign_attended  = g.get("offline_campaign_attended", "false").lower() == "true"
        competitor_activity = not product_scanned and not campaign_attended

        signal = Signal(
            id=str(uuid.uuid4()),
            entity_id=entity.id,
            signal_type="composite",
            severity=pest_severity,
            payload={
                "pest_alert_severity":      pest_severity,
                "weather_risk_score":       weather_risk_score,
                "weather_source":           "open-meteo" if weather_summary else "fallback",
                "weather_district":         rep_district,
                "weather_components":       weather_summary["components"] if weather_summary else None,
                "inventory_shortage_level": inventory_shortage,
                "inventory_pct":            inventory_pct,
                "ndvi_stress":              _seed_ndvi_stress(entity.id, rep_district, pest_severity),
                "ndvi_source":              "seeded_baseline",
                "crop_stage":               crop,
                "crop_stage_sensitivity":   crop_sensitivity,
                "competitor_activity":      competitor_activity,
                "complaint_open":           not campaign_attended and random.random() < 0.3,
                "revenue_potential":        round(revenue_potential, 2),
                "max_ltv":                  100000.0,
                "days_since_last_visit":    days_since,
            },
            created_at=datetime.utcnow(),
        )
        db.add(signal)

    db.commit()
    return len(entities), rep_district


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    db.query(Signal).delete()
    db.query(FarmerRetailer).delete()
    db.commit()

    rep_info = load_rep_data()
    last_visits = load_last_visits()

    print(f"Seeding {len(TARGET_REPS)} demo reps...")
    weather_cache = {}
    total_growers = 0
    rep_summary = []

    for rep_id in TARGET_REPS:
        if rep_id not in rep_info:
            print(f"  ⚠ {rep_id} not in reps_territory.csv — skipping")
            continue

        rep_row = rep_info[rep_id]
        last_visit = last_visits[rep_id]
        count, district = seed_rep(db, rep_id, rep_row, last_visit, weather_cache)
        total_growers += count
        rep_summary.append((rep_id, district, count))
        print(f"  ✓ {rep_id} ({district}): {count} growers")

    db.close()
    print(f"✓ Total: {total_growers} growers across {len(rep_summary)} reps")


if __name__ == "__main__":
    seed()