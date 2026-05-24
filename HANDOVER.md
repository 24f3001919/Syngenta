# Handover Notes

For Anany, Akshat, Kunal — and Ratnesh's future self after the hackathon.

This document captures what's fragile, what's tricky, what to leave alone, and where things live in the codebase. It's a complement to `README.md` (project overview) and `DEPLOYMENT.md` (how to deploy).

If something here contradicts another doc, this one is the freshest as of the Stage 2 push.

---

## Running locally

### Backend

```bash
cd ai-field-force/backend
python -m venv venv
.\venv\Scripts\Activate.ps1                 # Windows
source venv/bin/activate                    # Mac / Linux
pip install -r requirements.txt
cp .env.example .env                        # then fill in real values
uvicorn main:app --reload
```

### Frontend

```bash
cd ai-field-force/frontend
npm install
npm run dev
```

The frontend at `http://localhost:5173` expects the backend at `http://localhost:8000`. Override with `VITE_API_BASE_URL` in `frontend/.env.local`.

### Tests

```bash
cd ai-field-force/backend
pytest tests/ -v
```

26 tests, ~6 seconds. If anything fails, that's the first thing to fix before touching auth code.

---

## Required environment variables

The deployed copy on Render has these set. For local development they go in `ai-field-force/backend/.env` — that file is gitignored, never commit it.

### Backend

| Variable | Why it matters | Example |
|---|---|---|
| `JWT_SECRET` | Signs access tokens | any long random string |
| `JWT_REFRESH_SECRET` | Signs refresh tokens — must differ from JWT_SECRET | another long random string |
| `JWT_ACCESS_EXPIRE_MINUTES` | Access token lifetime | `15` |
| `JWT_REFRESH_EXPIRE_DAYS` | Refresh token lifetime | `30` |
| `OPENAI_API_KEY` | LLM briefings, recommended actions | `sk-...` |
| `DEV_MODE` | Returns OTPs in API response for demo | `true` for hackathon, `false` for real prod |
| `REFRESH_COOKIE_SAMESITE` | `none` on production (cross-origin Vercel→Render), `lax` locally | `none` |
| `REFRESH_COOKIE_SECURE` | `true` on production (HTTPS), `false` locally | `true` |
| `RESEND_API_KEY` | Email OTP delivery in production | `re_...` |
| `RESEND_FROM` | Email sender display name | `Kheti Compass <onboarding@resend.dev>` |
| `EMAIL_OTP_DEMO_REDIRECT` | Redirect demo-account OTPs to a real inbox | a Gmail we control |
| `TWO_FA_REQUIRED_ROLES` | Comma-separated roles forced through 2FA | `rep,manager,admin` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Local-dev email fallback (Render blocks outbound SMTP) | Gmail app-password setup |
| `GOOGLE_CLIENT_ID` | For Google Sign-In on web | `xxxxx.apps.googleusercontent.com` |

### Frontend

| Variable | Why it matters | Example |
|---|---|---|
| `VITE_API_BASE_URL` | Where to point API calls | `http://localhost:8000` locally |
| `VITE_GOOGLE_CLIENT_ID` | Same Google OAuth client | matches backend's `GOOGLE_CLIENT_ID` |
| `VITE_MOCK_MODE` | Bypass backend, use mock data | `false` (only set `true` to demo without a backend) |

---

## Render dashboard rules

Don't touch the following without coordinating:

- `JWT_SECRET` and `JWT_REFRESH_SECRET` — rotating these invalidates every logged-in session
- `REFRESH_COOKIE_SAMESITE` and `REFRESH_COOKIE_SECURE` — wrong values silently break login on production while leaving health checks passing
- `OPENAI_API_KEY` — burns budget if leaked
- `RESEND_API_KEY` — burns email quota if leaked

If you need to test changes to any of these, branch off `main`, deploy to a Render preview environment, and confirm there before promoting.

---

## What's fragile

### Render free tier ephemeral disk

The SQLite file is wiped on every redeploy. The startup hook in `main.py` reseeds when `farmers_retailers` is empty *or* when a composite signal is missing the `ndvi_stress` payload key (schema drift detection). Adding a new signal field requires extending that drift check. Stripping the check is fine if you migrate to Postgres.

### Render free tier outbound SMTP

Ports 25, 465, 587 are blocked. Email goes through Resend's HTTPS API instead. The factory in `core/auth/email_otp/sender.py` picks Resend over SMTP automatically when `RESEND_API_KEY` is set. Don't try to debug "why isn't Gmail SMTP working on Render" — it can't.

### Cross-origin cookies (Vercel → Render)

Refresh-token cookies require `SameSite=None; Secure` because the two domains are different. Browsers will silently refuse to send the cookie if either flag is wrong. Symptoms: login appears to work but the user is bounced back to `/login` after a few seconds when the access token expires.

### Token timezones

The fix is in place but worth flagging. `datetime.utcnow()` returns local time on some Windows configurations, which causes tokens to appear born-expired. All token-issuing code uses `datetime.now(timezone.utc)`. If you see "Signature has expired" within seconds of issuance, this is the culprit.

### React StrictMode double-firing

The dev frontend mounts most components twice in StrictMode (React's intentional behaviour). API calls in `useEffect` fire twice as a result, and uvicorn logs will show pairs of identical requests. This is dev-only — production runs each effect once.

### Refresh-token reuse detection is intentionally harsh

If a refresh token that has already been rotated is presented again, *every* active session for that rep is revoked with reason `reuse_detected`. This is the right behaviour — a replay means somewhere a token leaked — but it does mean if a user has two tabs open and the refresh rotates in tab A, tab B's stale cookie will trigger the kill switch. The frontend's queue-based refresh in `client.ts` is designed to prevent this in practice, but be aware.

---

## Where things live

### Backend

```
ai-field-force/backend/
├── api/routes/
│   ├── auth.py                 # login / refresh / logout / 2FA / register / google
│   ├── visits.py               # Today's Priorities, grower brief, NBA actions
│   ├── signals.py              # NDVI, pest, anomalies endpoints
│   ├── outcomes.py             # Outcome submission, sync queue
│   ├── manager.py              # Overview, rep detail, weight history
│   └── weights.py              # Manager-only weight tuning
├── services/
│   ├── auth_service.py         # Password, OTP, Google, 2FA, refresh-token logic
│   ├── visit_service.py        # Today's Priorities orchestration
│   ├── outcome_service.py      # Outcome ingestion, weight recalibration trigger
│   └── signal_service.py       # Anomaly detection wrapper
├── core/
│   ├── deterministic/
│   │   ├── explainer.py        # Reason codes + semantic family dedup
│   │   ├── override_rules.py   # VPS overrides (pest outbreak region, etc.)
│   │   └── anomaly_detector.py
│   ├── ml/
│   │   ├── priority_scorer.py  # The 9-signal VPS calculation
│   │   ├── feature_builder.py  # Signal payload → feature vector
│   │   ├── weights.py          # SIGNAL_WEIGHTS dict (sums to 1.0)
│   │   └── weight_updater.py   # Gradient-update from outcomes
│   ├── llm/
│   │   ├── briefing_chain.py   # gpt-4o-mini natural-language briefings
│   │   └── prompts/            # Per-language prompt templates
│   ├── integrations/
│   │   ├── ndvi.py             # Sentinel-2 L2A via Element84 STAC
│   │   ├── icar_pest.py        # ICAR/NCIPM/IMD/PPQS with baseline fallback
│   │   └── weather.py          # Open-Meteo
│   └── auth/
│       ├── security.py         # JWT issuance + verification, bcrypt
│       ├── dependencies.py     # FastAPI `get_current_rep` dependency
│       ├── email_otp/          # 2FA email OTP module (store + sender + factory)
│       └── otp/                # Phone OTP (legacy, console-only)
├── models/db/                  # SQLAlchemy ORM
├── db/
│   └── seed_data.py            # Idempotent seed with NDVI determinism
├── tasks/
│   └── signal_refresh.py       # Background refresh of NDVI + pest signals
├── tests/                      # 26 pytest tests
├── conftest.py                 # Shared test fixtures
└── main.py                     # FastAPI app + startup hooks (auto-reseed lives here)
```

### Frontend

```
ai-field-force/frontend/
├── src/
│   ├── api/                    # Axios client + endpoint wrappers
│   │   ├── client.ts           # ⚠️ refresh-token interceptor lives here
│   │   ├── auth.ts             # Login, logout, 2FA, refresh
│   │   ├── visits.ts           # Today's Priorities, grower brief
│   │   ├── signals.ts          # NDVI, pest, anomalies
│   │   └── adapters.ts         # Backend payload → frontend types
│   ├── context/
│   │   ├── AuthContext.tsx     # Login state, silent boot refresh
│   │   ├── LangContext.tsx     # ⚠️ ~850 translation keys live here
│   │   └── ThemeContext.tsx    # Dark mode toggle
│   ├── pages/
│   │   ├── Login.tsx           # ⚠️ 2FA OTP entry view added here
│   │   ├── Register.tsx
│   │   ├── rep/                # Today, GrowerDetail, Anomalies, Devices
│   │   └── manager/            # Overview, Reps, RepDetail, WeightsHistory
│   ├── components/             # PriorityCard, OutcomeForm, Header, etc.
│   ├── hooks/                  # useOfflineQueue, useDevice
│   └── types/                  # All shared TypeScript interfaces
├── vercel.json                 # SPA routing rewrites — don't delete
└── package.json
```

---

## How to add a new scoring signal

This is the most common change request. Step by step:

1. **Define the payload field** in `db/seed_data.py` — add a default value to the signal `payload` dict and a deterministic seed function if the value should be reproducible.
2. **Normalize the value** in `core/deterministic/signal_normalizer.py` — feature vector values must be in `[0.0, 1.0]`.
3. **Add to the feature vector** in `core/ml/feature_builder.py` — pull from `payload.get(your_field, 0.0)` with a sensible default.
4. **Add a weight** in `core/ml/weights.py` — rebalance other weights so `SIGNAL_WEIGHTS` sums to 1.0. There's an `assert` that will catch mistakes.
5. **Add reason codes** in `core/deterministic/explainer.py`:
   - Add to `resolve_reason_code()` with severity thresholds
   - Add to `REASON_FAMILY` if it conflicts with another signal at different severity
   - Add to `FAMILY_PRIORITY` listing strongest-to-weakest within the family
6. **Translate the reason codes** in `frontend/src/context/LangContext.tsx` — add keys like `reason.your_signal_severe` in all four languages.
7. **Update the schema drift check** in `main.py` — append your new field name to the sample-signal check so a redeploy triggers a fresh seed.
8. **Write tests** — at minimum a unit test in `tests/test_explainer.py` for the reason code, and a determinism test in `tests/test_seed.py`.

The NDVI signal added in Stage 2 follows this exact pattern and is a good reference.

---

## How to add a new translation key

1. Add the key to each of the four language dicts in `frontend/src/context/LangContext.tsx`. **Do not skip a language.** A missing key falls back to the key string itself, which is visible to users.
2. Use the key in JSX via `t('your.key')`.
3. For LLM-generated content (briefings, recommended actions), pass the user's language to the backend via the `Accept-Language` header (axios does this automatically via the request interceptor in `client.ts`).

Translation key convention: `screen.element.purpose` — e.g. `auth.2fa.enter_code`, `widget.satellite_title`, `reason.ndvi_high_stress`.

---

## How to deploy

`DEPLOYMENT.md` has the full procedure. The short version:

- **Backend.** Push to `main` on GitHub. Render auto-builds and redeploys. Watch the Logs tab for startup errors. The seed runs automatically.
- **Frontend.** Push to `main`. Vercel auto-builds.
- **Both deploys typically complete in 3–5 minutes.**

If a deploy breaks login, the fastest rollback is via Render's "Manual Deploy → Previous Successful Build" dropdown.

---

## Where to look when things break

| Symptom | Likely cause | Where to look |
|---|---|---|
| Login appears to work but bounces to `/login` | Refresh-cookie wrong SameSite/Secure | Render env vars |
| `/visits/today` returns empty list | Render reseed didn't run | Render logs around startup |
| OTP email not arriving | Resend account suspended, or wrong API key | Resend dashboard + Render env |
| All requests 401 | Access token expired or `JWT_SECRET` changed | Browser localStorage + Render env |
| 503 on `/auth/login/password` | Email sender failing | Render logs — search for `Resend send failed` or `SMTP send failed` |
| Frontend 404 on `/login` direct visit | `vercel.json` deleted | Restore `vercel.json` |
| Priority cards show wrong reasons after schema change | Drift check didn't trigger | Wipe seed locally (`del field_force.db`) and restart; on Render, update drift sentinel in `main.py` |
| Pytest fails with `KeyError: 'access_token'` | Login fixture not handling 2FA | `conftest.py` — `auth_headers` fixture must follow the 2FA branch |

---

## Notes for Kunal — dark mode

The dark mode toggle in `ThemeContext.tsx` is wired up and the `<html>` element receives `class="dark"` correctly. The issue is that `tailwind.config.js` was missing `darkMode: 'class'`, which means inline `dark:` utility classes don't compile. Adding that one line lights up the existing `dark:` classes throughout the codebase. Restart Vite after the change — Tailwind config is not hot-reloaded.

Beyond that, several components hardcode light-mode colours via classes like `bg-clay-50`, `text-forest-900`, `border-forest-100`. Each needs a `dark:` companion. The components most affected:

- `PriorityCard.tsx`
- `MetricCard.tsx`
- `HealthScoreCard.tsx`
- `pages/rep/Today.tsx` (KPI cards)
- `pages/rep/GrowerDetail.tsx` (info chips)

Estimated work: 60–90 minutes once the tailwind config fix is in place.

---

## Notes for Anany — Identity merge testing

The reverse-merge case (Google account first, then password registration with the same email) works in code but is sparsely tested. The path lives in `services/auth_service.py::login_or_signup_with_google`. The test file `tests/test_auth_password.py` covers the forward direction (password first, then Google link). Mirror those tests for the reverse direction when you have a slot.

---

## Notes for Akshat — Offline queue and outcomes

The offline outcome queue at `frontend/src/hooks/useOfflineQueue.tsx` uses `localStorage` keyed by `client_outcome_id`. On `online` events, the hook attempts to sync. Server-side dedup is keyed by `client_outcome_id` in `services/outcome_service.py`.

Two enhancements worth considering: a visible "pending sync" badge on the header (the count is already exposed), and a `/sync` page where the rep can manually retry failed entries with surfaced error messages.

---

## Contact

Anything in this document is wrong, missing, or unclear — Ratnesh Singh, `24f2008613@ds.study.iitm.ac.in`.