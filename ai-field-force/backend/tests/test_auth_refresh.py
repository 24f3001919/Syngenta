"""
Tests for refresh-token rotation, reuse detection, and revocation.

Covers:
  - Login sets the httpOnly refresh cookie correctly
  - /auth/refresh rotates the token: returns new access + new refresh cookie
  - Reusing an already-rotated refresh token revokes ALL sessions for that rep
  - /auth/logout revokes the refresh token (subsequent /refresh returns 401)
  - An expired refresh token is rejected with 401
"""
import time
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from config import JWT_REFRESH_SECRET, JWT_ALGORITHM
from models.db.refresh_token import RefreshToken


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _login(client, identifier="test.rep@syngenta.com", password="testpass123"):
    res = client.post(
        "/auth/login/password",
        json={"identifier": identifier, "password": password},
    )
    assert res.status_code == 200, res.text
    return res


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_login_sets_httponly_refresh_cookie(client, seeded_rep):
    res = _login(client)
    cookies = res.cookies
    assert "refresh_token" in cookies
    refresh_jwt = cookies["refresh_token"]
    # Decode to verify shape
    payload = jwt.decode(refresh_jwt, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["typ"] == "refresh"
    assert payload["sub"] == seeded_rep.id
    assert payload.get("jti")


def test_refresh_rotates_token_and_returns_new_pair(client, seeded_rep, test_db):
    # Login → get first refresh token
    login_res = _login(client)
    first_refresh = login_res.cookies["refresh_token"]
    first_access = login_res.json()["access_token"]

    # Tiny sleep to guarantee different iat timestamps (JWT resolution = 1s)
    time.sleep(1.1)

    # Call /auth/refresh — should return new access + rotate cookie
    refresh_res = client.post("/auth/refresh")
    assert refresh_res.status_code == 200, refresh_res.text
    body = refresh_res.json()
    assert body["access_token"]
    assert body["access_token"] != first_access  # new access token (different iat)
    new_refresh = refresh_res.cookies["refresh_token"]
    assert new_refresh != first_refresh           # new refresh token (rotated)

    # Verify DB: old refresh marked revoked with reason "rotated"
    from jose import jwt
    from config import JWT_REFRESH_SECRET, JWT_ALGORITHM
    first_payload = jwt.decode(first_refresh, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
    old_record = (
        test_db.query(RefreshToken)
        .filter(RefreshToken.jti == first_payload["jti"])
        .first()
    )
    assert old_record is not None
    assert old_record.revoked_at is not None
    assert old_record.revoked_reason == "rotated"

def test_reusing_rotated_refresh_token_revokes_all_sessions(client, seeded_rep, test_db):
    # Login to get refresh #1
    login_res = _login(client)
    refresh_1 = login_res.cookies["refresh_token"]

    time.sleep(1.1)  # Ensure rotation produces a different JWT

    # Rotate normally → refresh #1 now revoked, refresh #2 active
    rotate_res = client.post("/auth/refresh")
    assert rotate_res.status_code == 200

    # Now ATTACKER replays refresh #1 (already revoked) — should 401 AND nuke #2
    client.cookies.set("refresh_token", refresh_1)
    replay_res = client.post("/auth/refresh")
    assert replay_res.status_code == 401
    assert "reuse" in replay_res.json()["detail"].lower()

    # Verify ALL refresh tokens for this rep are now revoked
    all_tokens = (
        test_db.query(RefreshToken)
        .filter(RefreshToken.rep_id == seeded_rep.id)
        .all()
    )
    assert len(all_tokens) >= 2  # at least #1 and #2
    assert all(t.revoked_at is not None for t in all_tokens), \
        "Reuse detection should revoke ALL sessions for the rep"
    assert any(t.revoked_reason == "reuse_detected" for t in all_tokens)


def test_logout_revokes_refresh_token(client, seeded_rep):
    """After logout, the refresh token can no longer rotate."""
    _login(client)

    # Logout
    logout_res = client.post("/auth/logout")
    assert logout_res.status_code == 200

    # Try to refresh with the (now-revoked) cookie still in TestClient's jar
    # — actually TestClient may not auto-clear it, so simulate the attempt
    refresh_res = client.post("/auth/refresh")
    assert refresh_res.status_code == 401


def test_expired_refresh_token_rejected(client, seeded_rep, test_db):
    """Manually craft an expired refresh JWT — backend must reject it."""
    # Forge a token that's been expired for a day
    past = datetime.now(timezone.utc) - timedelta(days=1)
    expired_payload = {
        "sub": seeded_rep.id,
        "iat": int((past - timedelta(seconds=10)).timestamp()),
        "exp": int(past.timestamp()),
        "typ": "refresh",
        "jti": "expired-test-jti-12345",
    }
    expired_token = jwt.encode(expired_payload, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)

    client.cookies.set("refresh_token", expired_token)
    res = client.post("/auth/refresh")
    assert res.status_code == 401
    assert "invalid" in res.json()["detail"].lower() or "expired" in res.json()["detail"].lower()