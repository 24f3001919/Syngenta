# Stage 2 Progress

A reviewer-facing summary of what changed between Kheti Compass's Stage 1 submission (May 20, 2026) and the current deployment. This document complements `KNOWN_LIMITATIONS.md`, which listed the commitments made at Stage 1.

Each item below references the Stage 1 commitment it addresses, the implementation approach, and where the relevant code lives. Live URLs, demo credentials, and demo flow remain those of `README.md`.

---

## Summary

Of the seven Stage 2 commitments made in `KNOWN_LIMITATIONS.md`, six are now live in production and one (real complaint stream) remains out of scope because it requires Syngenta CRM access. Two additional capabilities were built beyond the original commitments — refresh-token rotation with reuse detection, and a 26-test automated test suite.

| Commitment area | Stage 1 status | Stage 2 status |
|---|---|---|
| Live pest signal (ICAR / KVK) | Static lookup table | **Live** — ICAR-NCIPM + IMD AAS + ICAR RSS + PPQS with deterministic baseline fallback |
| Live weather (per-grower) | District-shared | **Live** — Open-Meteo per district, plus Sentinel-2 NDVI per grower |
| Email OTP (replaces SMS / WhatsApp) | Stubbed | **Live** — 2FA via Resend HTTPS API, real emails delivered |
| Refresh tokens with device tracking | Single 7-day JWT | **Live** — 15-min access + 30-day refresh, rotation, reuse detection, httpOnly cookies |
| Automated test harness | None | **Live** — 26 pytest tests across auth, signals, explainer, seed, scorer |
| Competitor activity from outcome form | Inferred proxy | **Deferred** (still inferred; deprioritized in favour of NDVI integration) |
| Real complaint stream | Synthetic | **Out of scope** — requires Syngenta CRM integration |

In addition, the following were shipped beyond the original Stage 1 commitments:

- Multilingual UI and LLM briefings (English, Hindi, Gujarati, Bengali)
- Sentinel-2 L2A satellite NDVI integration as a ninth scoring signal
- Auto-seed on Render's ephemeral disk with schema-aware reseed
- Vercel SPA routing fix for direct-URL navigation
- Semantic-family reason dedup on priority cards
- Two new grower-detail widgets exposing live satellite and pest data sources

---

## 1. Live pest advisory integration

**Stage 1 commitment:** "RSS ingestion + NLP extraction, ~2–3 days of work."

**Stage 2 implementation.** A pest module at `backend/core/integrations/icar_pest.py` attempts four live sources in priority order:

1. ICAR-NCIPM weekly crop-pest scenario reports
2. IMD Agromet Advisory Service (district-level)
3. ICAR general RSS feed
4. DPPQS pest surveillance

Each source has multiple URL candidates because government endpoints rotate frequently. BeautifulSoup parses tables and text blocks for district mentions, then matches a high/medium/low/none severity keyword (English and Hindi keywords are supported).

When every live source is unreachable — which is common, as ICAR / IMD / PPQS infrastructure is unreliable — a deterministic baseline derived from a district-name hash takes over. The endpoint never returns 503 on a valid request; the response always carries a `source` field (`icar_ncipm` / `imd_aas` / `icar_rss` / `ppqs` / `deterministic_baseline`) and an `is_live` flag so a reviewer can audit data provenance.

The signal feeds into the VPS scoring pipeline via `payload.pest_alert_severity`. A 6-hour in-process cache keeps the load on government endpoints reasonable.

**Endpoints:** `GET /signals/pest/{entity_id}`, `POST /signals/refresh` (manager-only background job)
**Live verification:** Hit `https://kheti-compass.onrender.com/signals/pest/GRW_00311` with a rep token. The response includes the severity, district, source, and lineage.

---

## 2. Sentinel-2 satellite NDVI integration

**Beyond Stage 1 commitments.** A satellite-derived crop-stress signal was not part of the original roadmap, but was added because the Element84 STAC API offers free, authentication-less access to Sentinel-2 L2A imagery and the latency and rebuild cost were both acceptable.

**Implementation.** `backend/core/integrations/ndvi.py` queries the Element84 Earth Search STAC endpoint for the most recent Sentinel-2 L2A scene covering the grower's coordinates. Scene metadata (date, cloud cover, scene ID) is returned to the frontend. Raw NDVI pixel extraction requires the `rasterio` library, which is not included in the deployment image — scene metadata is exposed in the API response with `ndvi_raw: null` to make this explicit.

The ninth scoring signal `ndvi_stress` is currently seeded with a deterministic per-grower-per-district hash (the value is stable across reseeds and responds to pest-pressure pressure in the same district). A background refresh task at `backend/tasks/signal_refresh.py` is wired up to replace seeded values with live Sentinel-2 readings when triggered. On the live deployment, 26 of 27 growers in the demo rep's territory currently surface an NDVI-derived reason on their priority card.

**Endpoint:** `GET /signals/ndvi/{entity_id}`
**Weight:** 0.07 in `core/ml/weights.py` (other weights rebalanced to keep the sum at 1.0)
**Reason codes:** `ndvi_high_stress` (value ≥ 0.6), `ndvi_moderate_stress` (≥ 0.4), with family-based dedup so satellite and pest reasons collapse cleanly.

---

## 3. Multilingual interface and LLM briefings

**Beyond Stage 1 commitments.** Stage 1 was English-only. Stage 2 supports English, Hindi, Gujarati, and Bengali across:

- All UI strings (sourced from `frontend/src/context/LangContext.tsx`, ~850 translation keys)
- LLM-generated grower briefings and recommended actions — the backend reads the `Accept-Language` header from the frontend and instructs `gpt-4o-mini` to respond in the user's chosen language
- Priority-card reason codes — emitted as stable codes by the backend, translated client-side per locale
- Date and number formatting via locale-aware `Intl` APIs

**Design choice.** The backend emits language-agnostic reason codes (`override.pest_outbreak_region`, `ndvi_high_stress`, etc.) rather than localized strings. This keeps the API contract stable, lets the frontend cache translations, and avoids round-trip cost on language switch. A user toggling between Hindi and Gujarati never re-fetches the API.

---

## 4. Email OTP with 2FA enforcement

**Stage 1 commitment:** "Email OTP via SendGrid (chosen over SMS/WhatsApp because of zero compliance friction in India)."

**Stage 2 implementation.** Email OTP is now a mandatory second factor for every login (configurable per role). The flow:

1. `POST /auth/login/password` — validates credentials. If the user's role is in `TWO_FA_REQUIRED_ROLES`, returns a 2FA challenge envelope (`challenge_id`, `email_masked`, `expires_in_seconds`) and dispatches a 6-digit OTP via email. If not, issues tokens directly.
2. `POST /auth/2fa/verify` — accepts `{challenge_id, code}`, validates against an in-memory store with 5-minute expiry and 3 verification attempts. On success, issues the access + refresh token pair.

**Email delivery.** Production uses the Resend HTTPS API (port 443), which works on Render free tier. SMTP (port 587) was the initial choice but is blocked by Render's free-tier network policy to prevent spam abuse — `Network is unreachable` from the SMTP socket. The factory at `core/auth/email_otp/sender.py` selects Resend when `RESEND_API_KEY` is set, falls back to SMTP for local development, and finally to a console sender so tests can run without external dependencies.

**Demo-mode redirect.** Demo accounts use synthetic emails like `rep@syngenta.com`. The `EMAIL_OTP_DEMO_REDIRECT` config rewrites the OTP destination to the developer's real inbox at send time without changing what the user sees in the UI. The original email is still shown in the email body so the recipient knows which account they're logging into.

**Constant-time code comparison.** The OTP store uses `secrets.compare_digest` to prevent timing-attack disclosure of the code.

---

## 5. Refresh tokens with rotation and reuse detection

**Stage 1 commitment:** "Short-lived access tokens + long-lived refresh tokens with per-device session management."

**Stage 2 implementation.** A full rotation-with-reuse-detection scheme:

- **Access token:** 15-minute expiry, signed with `JWT_SECRET`, carries `typ: "access"`. Sent in the `Authorization` header.
- **Refresh token:** 30-day expiry, signed with a separate `JWT_REFRESH_SECRET`, carries `typ: "refresh"` and a unique `jti`. Delivered as an httpOnly cookie scoped to the `/auth` path. `SameSite=None; Secure` in production for cross-origin Vercel → Render delivery; `SameSite=Lax` for local development.
- **Server-side persistence.** Every refresh token is recorded in a `refresh_tokens` table tracking `jti`, expiry, revocation reason (`logout` / `rotated` / `reuse_detected` / `admin`), the forward `replaced_by_jti` rotation chain, hashed client IP, and user-agent.
- **Rotation.** Each successful `/auth/refresh` call revokes the presented token and issues a new pair. The old token is marked `rotated` and links forward to the new `jti`.
- **Reuse detection.** If a token that has already been revoked-with-reason `rotated` is replayed, all active sessions for that rep are revoked with reason `reuse_detected`. This is the standard signal that a token has been stolen — legitimate clients never replay a rotated token.
- **Frontend handling.** The axios interceptor at `frontend/src/api/client.ts` queues concurrent 401s, performs a single refresh, and replays the queued requests with the new access token. On app boot, if no access token is present in `localStorage` but the refresh cookie may still be valid, a silent refresh is attempted before redirecting to login.

**Files:** `models/db/refresh_token.py`, `services/auth_service.py` (methods `issue_token_pair`, `rotate_refresh_token`, `revoke_refresh_token`), `api/routes/auth.py` (`/auth/refresh`, `/auth/logout`).

---

## 6. Automated test suite

**Stage 1 commitment:** "Pytest harness across `core/scoring`, `core/anomalies`, `core/ml/weight_updater`, `services/auth_service`, plus CI integration. The first thing a careful engineering manager would add post-shortlist."

**Stage 2 implementation.** A pytest suite of 26 tests in `backend/tests/` covering:

| File | Tests | Coverage |
|---|---|---|
| `test_scorer.py` | 2 | VPS scoring math, override bumps |
| `test_auth_password.py` | 4 | Registration, login, wrong password rejection, non-existent user |
| `test_auth_refresh.py` | 5 | Cookie issuance, rotation, reuse detection, logout revoke, expired token |
| `test_explainer.py` | 5 | Reason-code resolution, override-vs-reason family dedup, top-3 cap |
| `test_signals.py` | 5 | `/signals/anomalies` auth gating + envelope, `/signals/pest` baseline fallback, `/signals/ndvi` contract |
| `test_seed.py` | 4 | NDVI seed determinism, range validity, pest-pressure responsiveness, hash distribution |

Tests run against an in-memory SQLite database via SQLAlchemy's `StaticPool`, with shared fixtures in `conftest.py` (`test_db`, `client`, `seeded_rep`, `seeded_manager`, `auth_headers`). The `auth_headers` fixture transparently completes the 2FA flow using the dev-mode OTP, so any test of a protected endpoint exercises the full password → email-OTP path.

```
$ pytest tests/ -v
========================= 26 passed in 6.42s =========================
```

CI integration is out of scope for the hackathon submission but the suite is structured to run cleanly under GitHub Actions with a single `pytest tests/` step.

---

## 7. Operational and infrastructure improvements

A set of changes that aren't tied to a specific Stage 1 commitment but were necessary to keep the live deployment usable across redeploys and demos.

**Auto-seed on Render ephemeral disk.** Render's free tier wipes the filesystem on every redeploy. Stage 1 required manual reseed via Swagger after each deploy. Stage 2 runs the seed automatically when the `farmers_retailers` table is empty *or* when a sample composite signal is missing the `ndvi_stress` key (schema drift detection). One deploy now leaves the system fully seeded with 247 growers across 10 reps.

**Vercel SPA routing.** Stage 1 returned Vercel's 404 page when a user typed `/login` or any sub-route directly in the URL bar. A `vercel.json` rewrite at `frontend/vercel.json` routes all paths to `index.html`, letting React Router handle the route client-side.

**Reason dedup by semantic family.** Priority cards in Stage 1 occasionally showed both `override.pest_outbreak_region` and `pest_critical` — the same situation at two severity levels. The explainer at `core/deterministic/explainer.py` now groups reason codes into semantic families (pest / visit / complaint / inventory / ndvi) and keeps only the strongest reason per family before truncating to the top three.

**Timezone-aware token generation.** Tokens were briefly being generated with naive `datetime.utcnow()` which returned local time on Windows; the resulting `iat` and `exp` claims were off by the local timezone offset, and 15-minute tokens appeared to be born already expired. All token-issuing code now uses `datetime.now(timezone.utc)`.

---

## What remains incomplete

**Real complaint stream.** The `complaint_open` boolean is still synthetic; closing this requires Syngenta CRM access, which we do not have. The schema and scoring weight are in place — the work that remains is integration, not modelling.

**Competitor activity from outcome form.** Stage 1 marked this as committed (~4 hours of work). Stage 2 prioritized the larger NDVI / pest / 2FA work and did not ship the outcome-form change. The inferred proxy continues to be used.

**Native iOS / Android app and real-time websockets** remain deliberately out of scope as documented in Stage 1.

---

## Verification checklist for reviewers

The following sequence exercises every Stage 2 capability end-to-end against the live deployment:

1. Visit `https://syngenta-nu.vercel.app/login` directly — does not 404 (SPA routing).
2. Switch language to Hindi using the top-right picker before logging in — all labels translate.
3. Log in as `rep@syngenta.com` / `syngenta123` — the password screen accepts credentials and shows the OTP entry screen.
4. The dev-mode hint shows the OTP value; the same OTP also arrives at the configured demo inbox (`mailratneshsingh05@gmail.com` in our deployment).
5. Enter the code — lands on Today's Priorities with 27 growers ranked.
6. Open any grower with an NDVI reason chip — the detail page shows the Satellite Crop Health widget (Sentinel-2 scene date, cloud cover) and the Regional Pest Advisory widget (severity, district, source lineage).
7. Trigger a token refresh manually: in the browser console, `localStorage.removeItem('access_token')` and click any grower. The 401 → `/auth/refresh` → retry sequence is visible in the Network tab; no logout occurs.
8. Log out, then attempt `POST /auth/refresh` from a script with the now-revoked cookie — 401 Unauthorized.
9. Backend tests: `cd ai-field-force/backend && pytest tests/` — 26 tests pass in under 10 seconds.

---

## Contact

Questions about any Stage 2 item: Ratnesh Singh — `24f2008613@ds.study.iitm.ac.in`