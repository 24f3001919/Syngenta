# Known Limitations

A reviewer-facing summary of what Kheti Compass does and does *not* do, what was resolved between Stage 1 and Stage 2, what remains open, and — for each open item — what fixing it would require and whether a fix is feasible. This file complements Section 7 of `solution_document.pdf` and `STAGE2_PROGRESS.md`.

Each item carries a status tag:

- **Resolved** — shipped in Stage 2; implementation detail in `STAGE2_PROGRESS.md`.
- **Open — fixable** — the work is well-defined and feasible with engineering time alone.
- **Open — blocked** — a fix requires resources outside our control (third-party access, regulatory clearance, or a real user base).
- **Out of scope** — deliberately not addressed.

---

## Data limitations

### Synthetic `complaint_open` signal

**What's missing.** The `complaint_open` boolean is generated synthetically: 30% of growers who haven't attended a recent campaign are flagged true. The hackathon dataset includes no complaint log.

**Status:** Open — blocked.

**What fixing it would require.** Integration with Syngenta's existing CRM or call-centre log. The integration surface is small — a single boolean per grower, refreshed daily — but the work requires:

1. API access to the upstream complaint system, including authentication credentials
2. A mapping table from CRM grower IDs to our `entity_id`
3. A scheduled job (or webhook handler) that updates `Signal.payload.complaint_open` when complaints are filed or resolved
4. A backfill of historical complaints for at least 90 days so the learner has signal

The schema is already in place: `complaint_open` is a first-class boolean column in the composite signal payload, weighted at 0.09 in `core/ml/weights.py`, with a corresponding override rule and reason code. The work that remains is integration, not modelling.

**Why we cannot fix it now.** No access to Syngenta CRM. This is the canonical blocker for the hackathon — an engineering fix is well-defined but requires institutional access we do not have.

---

### Proxy `competitor_activity` signal

**What's missing.** `competitor_activity` is inferred from the absence of `product_scan` and `offline_campaign_attended` flags in the grower record, not from rep-reported competitor sightings. A rep who actually saw a competitor product on a retailer's shelf has no way to record it.

**Status:** Open — fixable.

**What fixing it would require.** Three changes, approximately 2 hours of work:

1. Add a `competitor_seen: bool` field to the outcome form in `frontend/src/components/OutcomeForm.tsx`
2. Add a corresponding column to the `Outcome` model and migration
3. Update `services/outcome_service.py::record_outcome` to set the grower's `competitor_activity` flag when a rep checks the box

A future polish would be capturing *which* competitor product, but a boolean is sufficient for the scoring layer.

**Why we have not fixed it.** Stage 2 prioritized higher-impact work (Sentinel-2 NDVI integration, refresh-token rotation, email 2FA, automated test suite) within the time we had. The inferred proxy is honest enough for the demo — the source of the signal is documented and the override and reason-code paths work end-to-end. We expect to ship this fix in the first post-shortlist sprint.

---

### Static `pest_alert_severity` table

**Status:** Resolved. See `STAGE2_PROGRESS.md` §1. Live pest data is now fetched from ICAR-NCIPM, IMD AAS, ICAR RSS, and PPQS with a deterministic per-district baseline as fallback. Source provenance is exposed via `GET /signals/pest/{entity_id}`.

---

### District-granularity weather

**What's missing.** Open-Meteo is hit per district, not per grower. All 27 growers in Bikaner share `weather_risk_score=0.44`.

**Status:** Open — fixable, but superseded.

**What fixing it would require.** Open-Meteo accepts lat/lng directly and is rate-limit-tolerant for moderate query volumes. The change is:

1. Modify `core/integrations/weather.py::fetch_weather_for_district` to accept lat/lng instead of a district name
2. Update `db/seed_data.py` to call it per grower with each grower's coordinates
3. Adjust the cache key from district name to a rounded lat/lng grid (e.g. 10 km tiles) to avoid one API call per grower

Approximately 2-3 hours of work.

**Why we have not fixed it.** Stage 2 added a per-grower Sentinel-2 NDVI signal that captures local crop-health variability the per-grower weather signal would have surfaced. The marginal value of per-grower weather *after* NDVI is in place is small enough that we deprioritized this fix. The district-shared weather score remains in production.

---

## Authentication limitations

### OTP delivery is stubbed

**Status:** Resolved. See `STAGE2_PROGRESS.md` §4. Email OTP via the Resend HTTPS API is now live and enforced as a mandatory second factor on every password login. Phone OTP remains stubbed because of DLT compliance (see "Real SMS OTP" below).

---

### No refresh tokens

**Status:** Resolved. See `STAGE2_PROGRESS.md` §5. 15-minute access tokens + 30-day refresh tokens with rotation, reuse detection, and httpOnly cookie storage.

---

### No email verification on registration

**What's missing.** `POST /auth/register/password` accepts the supplied email as trusted. Anyone can register an account claiming to be `someone-else@example.com` and immediately start using it.

**Status:** Open — fixable.

**What fixing it would require.** Approximately 1.5 hours, leveraging the Resend infrastructure already in place for 2FA:

1. Add a `verification_token` field to `AuthIdentity` (or a small `email_verifications` table)
2. On `/auth/register/password`, set `verified_at=None` and dispatch a verification email with a tokenised link
3. New endpoint `GET /auth/verify-email?token=...` validates and sets `verified_at`
4. Gate login (or sensitive actions) on `verified_at IS NOT NULL`
5. Frontend: a verification-pending screen with a "resend email" button

The `verified_at` column already exists on `AuthIdentity` — the work is wiring it through the flow.

**Why we have not fixed it.** This was the next item on the queue after 2FA, but we ran out of time within the Stage 2 window. It is the cleanest follow-up — a 1-2 hour change with no architectural risk and an obvious user benefit.

---

### Identity merge testing is one-directional

**What's missing.** The forward path (rep registers with email + password, later logs in with Google) is covered by tests and a documented user flow. The reverse path (Google first, then password registration with the same email) works in code but has thin test coverage and has not been manually exercised end-to-end against the live deployment.

**Status:** Open — fixable.

**What fixing it would require.** Approximately 1 hour:

1. Two new tests in `tests/test_auth_password.py` exercising the Google-first → password-later path
2. A manual end-to-end check against staging or production
3. If a defect surfaces, the fix is likely in `services/auth_service.py::login_or_signup_with_google` where account linking decisions are made

**Why we have not fixed it.** Pure coverage gap, no urgency for the demo (the forward direction is what judges will test). Worth fixing before any post-hackathon pilot.

---

## Validation gap

### The learner is not yet field-validated

**What's missing.** Our seeded outcomes (8 records over 11 days, all from REP_0338) are enough to demonstrate the math works. A verified live recalibration produced real deltas (`complaint_open: −0.038`, `revenue_potential: +0.042`). These outcomes are **not** sufficient to claim the learned weights are *better* than the defaults.

**Status:** Open — blocked.

**What fixing it would require.** One of two approaches:

1. **Controlled live rollout** — assign half of REP_0338's territory to use Kheti Compass for 3-6 months while the other half operates as today, then compare visit-outcome quality. Requires either a real Syngenta pilot or a partner organisation with comparable field-rep operations.

2. **Simulated outcome stream** — calibrate a generative model against historical Syngenta outcome data, replay it in fast-forward against our scoring engine to produce statistically meaningful learner curves. Requires access to that historical data.

**Why we cannot fix it now.** Validation of a behavioural-learning system requires either real users over real time, or proprietary historical data. Neither is closeable by engineering alone within the hackathon window. We are transparent about this in `solution_document.pdf` Section 6.

---

## Testing gap

### No automated test harness in Stage 1

**Status:** Resolved. See `STAGE2_PROGRESS.md` §6. A 26-test pytest suite runs in ~6 seconds in the GitHub Actions CI pipeline on every push and pull request. The CI badge at the top of `README.md` reflects current status.

---

## Deliberately scoped out

These were considered and excluded with **no commitment to address them**. They remain reasonable additions only if user research warrants them after a Phase 1 pilot.

### Native iOS / Android app

**Why excluded.** A responsive Progressive Web App gives approximately 95% of the native experience (offline outcome storage, full-screen view, home-screen install via Add to Home Screen) at approximately 5% of the engineering cost of maintaining two native codebases. A native app is justifiable only when specific needs emerge — push notification reliability, deep camera integration for crop photography, or biometric authentication beyond what WebAuthn covers.

**Status:** Out of scope. Not a fix; a strategic call subject to user research.

---

### Real-time websockets

**Why excluded.** The data refresh cycle in the field-force workflow is measured in hours-to-days, not seconds. Reps consume the morning priority list once per day; managers review territory health weekly. Pull-to-refresh and the existing 15-minute background refresh job are sufficient. Websockets would add operational complexity (connection state, reconnection logic, Render's free-tier WebSocket support is limited) with no user benefit.

**Status:** Out of scope. Reconsider only if a real-time use case emerges (e.g. live competitor-sighting alerts across a regional team).

---

### Real SMS OTP via Twilio + DLT registration

**What's missing.** Phone OTP login (the legacy flow at `/auth/otp/send` and `/auth/otp/verify`) is end-to-end functional but no actual SMS is dispatched. In `DEV_MODE` the code is returned in the API response for demo purposes; in real production no code is sent.

**Status:** Out of scope. Functionally superseded by email 2FA.

**Why we cannot fix it within the hackathon.** India's Distributed Ledger Technology (DLT) regulation requires that every entity sending transactional SMS register with the Telecom Regulatory Authority and approve every message template. The process requires a registered business entity, takes 1-4 weeks of paperwork, and is not achievable by an individual student team within a hackathon. Email OTP (Stage 2: resolved) sidesteps this entirely with zero regulatory friction and was chosen as the deliberate substitute.

**If you wanted to fix it later** — register a Pvt Ltd entity, file with DLT, get template approvals, then integrate Twilio's WhatsApp Business API or any DLT-compliant SMS provider via the existing `core/auth/otp/factory.py` interface. The code path is already abstracted behind a sender interface; only the implementation changes.

---

## Summary table

| Limitation | Status | Effort to fix | Blocker |
|---|---|---|---|
| Static pest table | ✅ Resolved | — | — |
| Stubbed OTP | ✅ Resolved (email) | — | — |
| No refresh tokens | ✅ Resolved | — | — |
| No test harness | ✅ Resolved | — | — |
| Synthetic `complaint_open` | Open — blocked | ~1 day integration | Syngenta CRM access |
| Inferred `competitor_activity` | Open — fixable | ~2 hours | None |
| District-shared weather | Open — fixable | ~2-3 hours | None (deprioritized) |
| No email verification | Open — fixable | ~1.5 hours | None |
| Reverse identity merge testing | Open — fixable | ~1 hour | None |
| Learner field validation | Open — blocked | Months | Real users / proprietary data |
| Native mobile app | Out of scope | — | Strategic call |
| Real-time websockets | Out of scope | — | No use case |
| Real SMS OTP | Out of scope | 1-4 weeks regulatory | DLT compliance |

---

## What we are *not* hiding

If a reviewer reads `backend/core/auth/email_otp/sender.py`, they will see the Resend HTTPS API integration with a console-sender fallback — exactly what this file states.

If a reviewer reads `db/seed_data.py`, they will see synthetic complaint generation alongside the deterministic NDVI seed — exactly what this file states.

If a reviewer runs `pytest tests/`, they will see 26 passing tests in under 10 seconds — exactly what this file states.

If a reviewer inspects the Render dashboard, they will see SMTP fallback configured alongside Resend because Render free tier blocks outbound SMTP ports (documented in `HANDOVER.md`) — exactly what the codebase reveals.

Being upfront here means there is no surprise for the reviewer and no defensive answer needed during evaluation.

---

## Contact

Questions about any limitation: Ratnesh Singh — `24f2008613@ds.study.iitm.ac.in`