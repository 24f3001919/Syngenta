# Kheti Compass
[![Backend Tests](https://github.com/Ratnesh-101/Syngenta/actions/workflows/test.yml/badge.svg)](https://github.com/Ratnesh-101/Syngenta/actions/workflows/test.yml)
[![Backend on Render](https://img.shields.io/badge/backend-Render-46E3B7?logo=render&logoColor=white)](https://kheti-compass.onrender.com/docs)
[![Frontend on Vercel](https://img.shields.io/badge/frontend-Vercel-000000?logo=vercel&logoColor=white)](https://syngenta-nu.vercel.app)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](https://react.dev)

**An AI-Guided Visit Priority System for Syngenta Field Reps**

Team Farmlytics — IIT Madras BS Degree in Data Science & Applications
Syngenta AgriTech Hackathon 2026 — Track: AI-Guided Field Force Intelligence

---

## What this is

Kheti Compass tells a Syngenta field rep, every morning: *who should I visit first today, and why?*

Each grower in the rep's territory gets a Visit Priority Score (0–100) computed from eight signals — weather, pest pressure, retailer inventory, visit cadence, complaints, crop stage, revenue potential, and competitor activity. The top three contributing signals are surfaced as `reasons[]` next to each score. Anomalies (overdue visits, open complaints, competitor sightings) appear alongside the ranking. The system learns from outcomes — every visit's rating adjusts the eight signal weights through a gradient update, and managers can browse the Learning Trail to see exactly what changed and why.

The brief asked for an "AI-guided field force intelligence" system. We read it as: *make the data Syngenta already collects show up in the rep's pocket every morning, ranked, with reasoning the rep can act on or argue with.*

---

## Live deployment

| Service | URL |
|---|---|
| Frontend | https://syngenta-nu.vercel.app |
| Backend | https://kheti-compass.onrender.com |
| API docs (Swagger) | https://kheti-compass.onrender.com/docs |

Free-tier hosting. First request after 15 minutes of idle takes ~30s to cold-start (Render free tier behavior). UptimeRobot keeps the backend warm during evaluation.

### Demo credentials

**Field rep accounts** (password: `syngenta123`):

- `rep@syngenta.com` — REP_0338, Bikaner, Rajasthan (primary demo rep, also linked to phone `9999999999`)
- `rep2@syngenta.com` — REP_0472, Sikar, Rajasthan
- `rep3@syngenta.com` — REP_0394, Mehsana, Gujarat
- `rep4@syngenta.com` — REP_0426, Meerut, Uttar Pradesh

**Manager account:**

- `manager@syngenta.com` / `manager123` — oversees all 10 reps (247 growers across Rajasthan, Gujarat, UP, Bihar)

---

## Stack

- **Backend:** FastAPI 0.115 + SQLAlchemy 2.0 + SQLite (Python 3.11)
- **Frontend:** React 18 + Vite 5 + TypeScript + Tailwind CSS
- **LLM:** OpenAI `gpt-4o-mini` for natural-language briefings (deterministic scoring is LLM-free)
- **Weather:** Open-Meteo (live, no API key required)
- **Auth:** JWT-based, supporting email+password (bcrypt), phone OTP, and Google OAuth — all converging on the same user identity
- **Hosting:** Render (backend) + Vercel (frontend), free tiers
- **Architecture:** Strict `routes → services → core` layering; the scoring engine has no awareness of HTTP or DB

---

## Repository layout

```
Syngenta/
├── ai-field-force/
│   ├── backend/                # FastAPI app
│   │   ├── api/routes/         # HTTP endpoints (auth, visits, signals, outcomes, weights, manager)
│   │   ├── services/           # Workflow orchestration
│   │   ├── core/               # Pure functions: scoring, anomalies, ML
│   │   ├── models/db/          # SQLAlchemy ORM models
│   │   ├── db/                 # Seed scripts + SQLite file
│   │   ├── main.py             # FastAPI app + startup hooks
│   │   ├── requirements.txt
│   │   ├── runtime.txt         # Python 3.11.10 for Render
│   │   ├── Procfile            # Render start command
│   │   └── .env.example
│   └── frontend/               # React + Vite + TypeScript
│       ├── src/
│       │   ├── api/            # Backend adapter layer
│       │   ├── pages/          # rep/ + manager/ flows
│       │   ├── components/     # Shared UI
│       │   ├── context/        # Auth + Theme providers
│       │   └── hooks/          # useOfflineQueue, useDevice
│       ├── package.json
│       ├── vite.config.ts
│       └── .env.local.example
├── README.md                   # this file
├── DEPLOYMENT.md               # deployment-specific notes
└── solution_document.pdf       # the 9-page solution document
```

---

## Quickstart — local development

### Prerequisites

- Python 3.11+ (3.13 also works)
- Node.js 20.x LTS (Vite has known issues with 24.x — see DEPLOYMENT.md)
- An OpenAI API key (for the briefing endpoints; the rest of the system works without it)

### Backend

```bash
cd ai-field-force/backend
python -m venv venv
source venv/bin/activate           # Linux/macOS
# OR  venv\Scripts\Activate.ps1    # Windows PowerShell

pip install -r requirements.txt

# Create your .env from the example
cp .env.example .env               # Linux/macOS
# OR  Copy-Item .env.example .env  # Windows PowerShell

# Fill in OPENAI_API_KEY and JWT_SECRET in .env

# Seed the demo data (10 reps, 247 growers, fetches real weather from Open-Meteo)
python -m db.seed_data

# Run the dev server
uvicorn main:app --reload
# Backend now at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

### Frontend

In a separate terminal:

```bash
cd ai-field-force/frontend
npm install

# Create your .env.local from the example
cp .env.local.example .env.local   # Linux/macOS
# OR  Copy-Item .env.local.example .env.local  # Windows PowerShell

# Edit .env.local — set VITE_API_BASE_URL to http://localhost:8000 for local backend,
# or to https://kheti-compass.onrender.com to use the live backend.

npm run dev
# Frontend now at http://localhost:5173
```

Log in at `http://localhost:5173` with any of the demo credentials above.

---

## Key endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/auth/login` | Email + password login |
| `POST` | `/auth/otp/send` | Issue phone OTP (stubbed for Stage 1; demo phone `9999999999`) |
| `POST` | `/auth/otp/verify` | Verify OTP and issue JWT |
| `POST` | `/auth/google` | Google OAuth ID token verification |
| `GET`  | `/visits/today` | Ranked priority list with `reasons[]`, anomalies, confidence labels |
| `POST` | `/visits/{id}/brief` | LLM-generated morning briefing for a grower |
| `GET`  | `/signals/anomalies` | First-class anomaly events |
| `POST` | `/outcomes/sync` | Idempotent outcome capture (offline-first) |
| `GET`  | `/manager/overview` | Territory health KPIs across managed reps |
| `GET`  | `/weights/current` | Current 8 signal weights |
| `GET`  | `/weights/history` | The Learning Trail — every weight update with delta |
| `POST` | `/weights/recalibrate` | Manager-gated re-aggregation over recent outcomes |

Full API at `/docs` (Swagger UI) on any running instance.

---

## Documentation

- **`solution_document.pdf`** — 9-page solution document covering problem interpretation, system design, scoring engine, UX decisions, business value, limitations, team, and appendix
- **`DEPLOYMENT.md`** — how the live deployment is configured (Render + Vercel + UptimeRobot)
- **`/docs` (Swagger UI)** on any running backend instance

---

## Team

| Member | Role |
|---|---|
| **Ratnesh Singh** (primary contact) | Backend Lead — scoring engine, manager dashboard, learning system, deployment, document |
| **Kunal Kumar Pathak** | Frontend Lead — React app, mobile-first UX, dark mode, manager flows |
| **Anany Katyayan** | Backend Support — JWT auth, multi-method login, identity merging |
| **Akshat Om Chaturvedi** | Frontend Support — outcome capture UI, offline queue, sync indicator |

Contact: `24f2008613@ds.study.iitm.ac.in`

---

## License

This project was built for the Syngenta AgriTech Hackathon 2026 evaluation. All rights reserved by Team Farmlytics. Code may be reviewed by Syngenta and IIT Madras evaluators.