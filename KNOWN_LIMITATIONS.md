# Known Limitations

A reviewer-facing summary of what Kheti Compass does and does *not* do, what was resolved between Stage 1 and Stage 2, and what remains out of scope. This file complements Section 7 of `solution_document.pdf` and `STAGE2_PROGRESS.md`.

Each item carries a status tag:

- **Resolved** — shipped in Stage 2; see `STAGE2_PROGRESS.md` for implementation detail.
- **Stage 2: committed** — still in progress or de-scoped explicitly.
- **Out of scope** — deliberately not addressed; reasons given.

---

## Data limitations

### Synthetic `complaint_open` signal

The 30% rate of `complaint_open=true` for growers who haven't attended a recent campaign is a placeholder for a real complaint stream. The hackathon dataset does not include a complaint log. **[Out of scope — requires Syngenta CRM integration]**. The schema has `complaint_open` as a first-class boolean signal and the scoring weight is wired in; the work that remains is integration, not modelling.

### Proxy `competitor_activity` signal

Inferred from the absence of `product_scan` and `offline_campaign_attended` flags in the grower record. A true signal would come from rep-reported competitor sightings. **[Stage 2: committed — deferred]**. The work (~4 hours, adding a checkbox to the outcome form and a flag to the schema) was deprioritized in favour of the larger NDVI and 2FA work. The inferred proxy continues to be used.

### Static `pest_alert_severity` table

**[Resolved]**. Live pest data is now fetched from ICAR-NCIPM, IMD AAS, ICAR RSS, and PPQS with a deterministic per-district baseline as fallback. The integration is at `backend/core/integrations/icar_pest.py`. Source provenance is exposed via the `source` and `is_live` fields on `GET /signals/pest/{entity_id}`.

### District-granularity weather

Open-Meteo integration is live, but we cache results per district rather than per grower. All 27 growers in Bikaner share the same `weather_risk_score=0.44`. **[Stage 2: committed — superseded]**. Per-grower granularity for weather is still a missing item, but Stage 2 added a per-grower Sentinel-2 NDVI signal that captures local crop-health variability the weather signal would have missed. See `STAGE2_PROGRESS.md` §2.

---

## Authentication limitations

### OTP delivery is stubbed

**[Resolved]**. Email OTP via the Resend HTTPS API is now live. Phone OTP remains stubbed (DLT compliance prevents real SMS), but email OTP is enforced as a mandatory second factor on every password login. Demo accounts route OTPs to a developer inbox via `EMAIL_OTP_DEMO_REDIRECT` so the flow can be exercised end-to-end during demos without changing user-visible email addresses. See `STAGE2_PROGRESS.md` §4.

### No refresh tokens

**[Resolved]**. 15-minute access tokens + 30-day refresh tokens with rotation and reuse detection. Refresh tokens are stored in an httpOnly cookie scoped to `/auth`; each rotation revokes the previous token and links it forward via `replaced_by_jti`; a replay of any rotated token nukes all sessions for that rep. See `STAGE2_PROGRESS.md` §5.

### No email verification on registration

**[Stage 2: committed — partially resolved]**. The SMTP infrastructure is now in place via Resend, and the same delivery pipeline used for 2FA can carry a verification email. The frontend flow and the dedicated verification endpoint are not yet implemented.

### Identity merge testing is one-directional

A rep who signs up with email + password and later logs in with Google gets merged into one account. The reverse direction (Google first, then password) works in code but is not as thoroughly tested. **[Stage 2: committed — deferred]**. Test coverage for the reverse direction would be ~0.5 day of work.

---

## Validation gap

### The learner is not yet field-validated

Our seeded outcomes (8 total over 11 days, all from REP_0338) are sufficient to demonstrate the math works — a verified live recalibration produced real deltas (`complaint_open: −0.038`, `revenue_potential: +0.042`). They are **not** sufficient to claim the learned weights are *better* than the defaults. A real validation requires either:

- A controlled rollout (some reps with the system, some without) tracked over 3–6 months, or
- A simulated outcome stream calibrated against historical Syngenta data, replayed in fast-forward

**[Out of scope]**. This gap cannot be closed by engineering alone. It requires a real deployment.

---

## Testing gap

### No automated test harness

**[Resolved]**. A 26-test pytest suite now lives at `backend/tests/` covering auth flows (password, refresh-token rotation, reuse detection, logout, expired tokens), the explainer (reason code resolution, semantic-family dedup, top-3 cap), the signals endpoints (`/anomalies`, `/pest`, `/ndvi`), the deterministic NDVI seeder, and the VPS scoring math. Runs in ~6 seconds against an in-memory SQLite database. See `STAGE2_PROGRESS.md` §6.

CI integration is the remaining gap; the suite is structured to run cleanly under GitHub Actions with a single `pytest tests/` step.

---

## Deliberately scoped out

These were considered and excluded with **no Stage 2 commitment** — they remain reasonable additions only if user research warrants them after a Phase 1 pilot.

### Native iOS / Android app

A responsive PWA gives ~95% of the native experience (offline storage, full-screen, home-screen install) at ~5% of the engineering cost. We would only build a native app if specific needs emerge — push notification reliability, deep camera integration for crop photos, or biometric login.

### Real-time websockets

Considered for the manager dashboard, ruled out because the data refresh cycle is hours-to-days, not seconds. Pull-to-refresh suffices.

### Real SMS OTP (Twilio + DLT)

Listed as a Stage 1 commitment but blocked by India's DLT (telemarketing) registration which takes weeks of paperwork and a registered entity. Email OTP (Stage 2: resolved above) sidesteps this entirely with zero regulatory friction.

---

## What we are *not* hiding

If a reviewer reads `backend/core/auth/email_otp/sender.py`, they will see the Resend HTTPS API integration with a console-sender fallback — exactly what this file states.

If a reviewer reads `db/seed_data.py`, they will see synthetic complaint generation alongside the deterministic NDVI seed — exactly what this file states.

If a reviewer runs `pytest tests/`, they will see 26 passing tests in under 10 seconds — exactly what this file states.

If a reviewer looks at the Render dashboard, they will see SMTP fallback configured alongside Resend because Render free tier blocks outbound SMTP ports (documented in `HANDOVER.md`) — exactly what the codebase reveals.

Being upfront here means there is no surprise for the reviewer and no defensive answer needed during evaluation.

---

## Contact

Questions about any limitation: Ratnesh Singh — `24f2008613@ds.study.iitm.ac.in`