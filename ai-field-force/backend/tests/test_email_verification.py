"""
Tests for email verification on registration.

Covers:
  - Registration creates a verification token row in the DB
  - Valid token → 200 + identity.verified_at set
  - Invalid/garbage token → 400
  - Already-used token → 400
"""
import pytest
from models.db.auth_identity import AuthIdentity
from models.db.email_verification import EmailVerification
from core.auth.email_verification import store as email_verification_store

# ── helpers ───────────────────────────────────────────────────────────────────

def _register(client, suffix: str):
    """Register a fresh unverified user. Returns the HTTP response."""
    return client.post(
        "/auth/register/password",
        json={
            "name":     f"Verify User {suffix}",
            "email":    f"verify.{suffix}@example.com",
            "phone":    f"91111{suffix}",
            "password": "password123",
        },
    )


def _password_identity(test_db, suffix: str) -> AuthIdentity:
    return (
        test_db.query(AuthIdentity)
        .filter(
            AuthIdentity.identifier == f"verify.{suffix}@example.com",
            AuthIdentity.provider   == "password",
        )
        .first()
    )


# ── tests ─────────────────────────────────────────────────────────────────────

def test_registration_creates_verification_token(client, test_db):
    """Registering a new user must persist an unused EmailVerification row."""
    res = _register(client, "10001")
    assert res.status_code == 201

    identity = _password_identity(test_db, "10001")
    assert identity is not None, "Password identity not found after registration"

    record = (
        test_db.query(EmailVerification)
        .filter(EmailVerification.auth_identity_id == identity.id)
        .first()
    )
    assert record is not None, "No EmailVerification row created on registration"
    assert record.used_at is None,   "Token should not be consumed yet"
    assert record.expires_at is not None


def test_verify_endpoint_with_valid_token_marks_verified(client, test_db):
    """POSTing a valid token to /auth/verify-email returns 200 and sets verified_at."""
    _register(client, "10002")

    identity = _password_identity(test_db, "10002")
    assert identity is not None

    # Issue a fresh token directly (bypasses email transport entirely)
    plain_token, _ = email_verification_store.issue(test_db, identity.id)

    res = client.post("/auth/verify-email", json={"token": plain_token})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    body = res.json()
    assert body["email_verified_at"] is not None, \
        "email_verified_at must be set in response after verification"

    # Confirm persisted in DB
    test_db.refresh(identity)
    assert identity.verified_at is not None, \
        "verified_at must be set on the AuthIdentity row after verification"


def test_verify_endpoint_with_invalid_token_returns_400(client, test_db):
    """A garbage token must return 400, not 500."""
    res = client.post(
        "/auth/verify-email",
        json={"token": "this-is-not-a-real-token-xxxxxxxxxxxxxxxxxxx"},
    )
    assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"


def test_verify_endpoint_rejects_already_used_token(client, test_db):
    """Replaying a token that was already consumed must return 400."""
    _register(client, "10004")

    identity = _password_identity(test_db, "10004")
    assert identity is not None

    plain_token, _ = email_verification_store.issue(test_db, identity.id)

    # First use — must succeed
    res1 = client.post("/auth/verify-email", json={"token": plain_token})
    assert res1.status_code == 200, f"First verify failed: {res1.text}"

    # Replay — must be rejected
    res2 = client.post("/auth/verify-email", json={"token": plain_token})
    assert res2.status_code == 400, \
        f"Replayed token should return 400, got {res2.status_code}: {res2.text}"