# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db.session import engine, Base, SessionLocal
from api.routes import visits, farmers, signals, outcomes, weights, auth, devices, manager

# Import all models so SQLAlchemy knows about them before creating tables
from models.db import farmers        as farmers_model
from models.db import signal         as signal_model
from models.db import outcome        as outcome_model
from models.db import visit          as visit_model
from models.db import rep            as rep_model
from models.db import auth_identity  as auth_identity_model
from models.db import device         as device_model
from models.db import weight_history as weight_history_model

from models.db.rep import Rep
from models.db.auth_identity import AuthIdentity
from models.db.outcome import Outcome
from models.db.device import Device
from models.db.weight_history import WeightHistory
from models.db.farmers import FarmerRetailer
from services.auth_service import AuthService
from db.seed_demo_outcomes import seed_demo_outcomes
from db.seed_data import seed as seed_growers
from models.db.signal import Signal as _Signal

app = FastAPI(title="Field Force Copilot", version="0.8.0")

# ---------- CORS ----------
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ---------- Demo rep accounts ----------
DEMO_LOGIN_REPS = [
    ("rep@syngenta.com",  "syngenta123", "REP_0338", "Demo Rep"),
    ("rep2@syngenta.com", "syngenta123", "REP_0472", "Sikar Rep"),
    ("rep3@syngenta.com", "syngenta123", "REP_0394", "Mehsana Rep"),
    ("rep4@syngenta.com", "syngenta123", "REP_0426", "Meerut Rep"),
]

MANAGER_REP_IDS = [
    "REP_0338", "REP_0472", "REP_0373", "REP_0394", "REP_0317",
    "REP_0426", "REP_0325", "REP_0372", "REP_0105", "REP_0129",
]


@app.on_event("startup")
def startup():
    # Wipe + recreate the tables we own. Signals / farmers / visits are
    # managed by db.seed_data and seeded below if missing.
    WeightHistory.__table__.drop(bind=engine, checkfirst=True)
    Outcome.__table__.drop(bind=engine, checkfirst=True)
    Device.__table__.drop(bind=engine, checkfirst=True)
    AuthIdentity.__table__.drop(bind=engine, checkfirst=True)
    Rep.__table__.drop(bind=engine, checkfirst=True)

    Base.metadata.create_all(bind=engine)
    print("✓ Database tables ready (auth + outcomes + devices + weight_history migrated)")

    db = SessionLocal()
    try:
        svc = AuthService()

        # ---------- Seed rep accounts ----------
        for email, password, rep_id, name in DEMO_LOGIN_REPS:
            phone = "9999999999" if rep_id == "REP_0338" else None
            svc.ensure_seed_rep(
                db,
                rep_id=rep_id,
                name=name,
                email=email,
                phone=phone,
                password=password,
                role="rep",
                managed_rep_ids=[],
            )
        print(f"✓ {len(DEMO_LOGIN_REPS)} demo rep accounts ensured")
        print(f"   Primary: rep@syngenta.com / syngenta123 (REP_0338, also phone 9999999999)")
        for email, _, rep_id, _ in DEMO_LOGIN_REPS[1:]:
            print(f"   Also:    {email} / syngenta123 ({rep_id})")

        # ---------- Seed manager account ----------
        svc.ensure_seed_rep(
            db,
            rep_id=None,
            name="Demo Manager",
            email="manager@syngenta.com",
            phone=None,
            password="manager123",
            role="manager",
            managed_rep_ids=MANAGER_REP_IDS,
        )
        print(f"✓ Demo manager ensured (manager@syngenta.com / manager123)")
        print(f"   Manages {len(MANAGER_REP_IDS)} reps across 5+ states")

        # ---------- Seed growers + signals if DB is empty ----------
        # Idempotent: skips if growers already present, runs full seed if not.
        # This is what populates the priority list on Render's ephemeral disk.
        # ---------- Seed growers + signals if DB is empty OR stale ----------
        # Trigger reseed if growers exist but their signal payloads lack newer keys.
        # This handles schema migrations on Render's ephemeral disk without manual wipes.

        existing_growers = db.query(FarmerRetailer).count()
        needs_reseed = existing_growers == 0

        if not needs_reseed:
            # Check if signal payload schema is current (has ndvi_stress)
            sample = db.query(_Signal).filter(_Signal.signal_type == "composite").first()
            if sample and isinstance(sample.payload, dict) and "ndvi_stress" not in sample.payload:
                print("⚠ Signal payloads missing ndvi_stress key — forcing reseed for schema sync")
                needs_reseed = True

        if needs_reseed:
            print("⚠ Running full grower + signal seed...")
            db.close()
            try:
                seed_growers()
                print("✓ Growers + signals seeded")
            except Exception as e:
                print(f"⚠ Grower seed failed: {e}")
            db = SessionLocal()
        else:
            print(f"✓ Skipping grower seed — {existing_growers} growers already in DB with current schema")

        # ---------- Seed demo outcomes ----------
        seed_result = seed_demo_outcomes(db)
        print(f"✓ Demo outcomes seeded: created={seed_result['created']}, skipped={seed_result['skipped']}")
    finally:
        db.close()


# Routers
app.include_router(auth.router,     prefix="/auth",     tags=["Auth"])
app.include_router(visits.router,   prefix="/visits",   tags=["Visits"])
app.include_router(farmers.router,  prefix="/farmers",  tags=["Farmers"])
app.include_router(signals.router,  prefix="/signals",  tags=["Signals"])
app.include_router(outcomes.router, prefix="/outcomes", tags=["Outcomes"])
app.include_router(weights.router,  prefix="/weights",  tags=["Weights"])
app.include_router(devices.router,  prefix="/devices",  tags=["Devices"])
app.include_router(manager.router,  prefix="/manager",  tags=["Manager"])


@app.get("/")
def root():
    return {"status": "ok", "project": "Field Force Copilot", "version": "0.8.0"}