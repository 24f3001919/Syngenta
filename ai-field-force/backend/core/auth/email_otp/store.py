"""
In-memory store for active 2FA email-OTP challenges.

Each challenge maps a randomly-generated `challenge_id` to:
  - rep_id (uuid PK of the Rep)
  - email (where the OTP was sent — for audit / masked display)
  - code (the actual 6-digit OTP)
  - expires_at
  - attempts_remaining

We keep this in-memory because:
  - Challenges are short-lived (5 min)
  - Volume is tiny
  - Avoids DB writes on the critical login path
  - Render free tier ephemeral disk would lose persisted state on restart anyway

On a real production deployment with multiple backend instances, this would
move to Redis. For the hackathon single-instance Render deploy, this is fine.
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass
from typing import Optional

from config import (
    OTP_EMAIL_LENGTH,
    OTP_EMAIL_EXPIRY_SECONDS,
    OTP_EMAIL_MAX_ATTEMPTS,
)


@dataclass
class Challenge:
    challenge_id:       str
    rep_id:             str
    email:              str
    code:               str
    expires_at_ts:      float
    attempts_remaining: int

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at_ts


class EmailOtpStore:
    def __init__(self) -> None:
        self._lock: threading.Lock                = threading.Lock()
        self._by_id: dict[str, Challenge]          = {}

    def issue(self, rep_id: str, email: str) -> Challenge:
        """Generate a new OTP challenge. Returns the Challenge object so caller
        can read the code and dispatch the email."""
        with self._lock:
            self._purge_expired_locked()

            challenge_id = secrets.token_urlsafe(24)
            code = "".join(secrets.choice("0123456789") for _ in range(OTP_EMAIL_LENGTH))
            challenge = Challenge(
                challenge_id=challenge_id,
                rep_id=rep_id,
                email=email,
                code=code,
                expires_at_ts=time.time() + OTP_EMAIL_EXPIRY_SECONDS,
                attempts_remaining=OTP_EMAIL_MAX_ATTEMPTS,
            )
            self._by_id[challenge_id] = challenge
            return challenge

    def verify(self, challenge_id: str, code: str) -> Optional[Challenge]:
        """Return the Challenge if code matches; consume it on success.

        Decrements attempts_remaining on bad code; deletes challenge when
        attempts exhausted. Returns None on any failure.
        """
        with self._lock:
            self._purge_expired_locked()
            challenge = self._by_id.get(challenge_id)
            if not challenge:
                return None
            if challenge.is_expired:
                self._by_id.pop(challenge_id, None)
                return None

            # Constant-time compare to avoid timing-attack leak
            if secrets.compare_digest(challenge.code, code):
                self._by_id.pop(challenge_id, None)
                return challenge

            challenge.attempts_remaining -= 1
            if challenge.attempts_remaining <= 0:
                self._by_id.pop(challenge_id, None)
            return None

    def peek(self, challenge_id: str) -> Optional[Challenge]:
        """Read a challenge without consuming. Used to look up email_masked
        for the response. Returns None if not found or expired."""
        with self._lock:
            self._purge_expired_locked()
            challenge = self._by_id.get(challenge_id)
            if challenge and not challenge.is_expired:
                return challenge
            return None

    def invalidate(self, challenge_id: str) -> None:
        """Drop a challenge (used on logout race or admin intervention)."""
        with self._lock:
            self._by_id.pop(challenge_id, None)

    def _purge_expired_locked(self) -> None:
        """Caller MUST hold _lock. Removes expired entries to bound memory."""
        now = time.time()
        expired = [cid for cid, c in self._by_id.items() if c.expires_at_ts < now]
        for cid in expired:
            self._by_id.pop(cid, None)


# Module-level singleton — one store per backend process
email_otp_store = EmailOtpStore()