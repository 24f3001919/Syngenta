"""
Tests for password-based registration and login.

Covers:
  - Successful registration creates a Rep + access token
  - Successful login returns 200 + token + sets refresh cookie
  - Wrong password returns 401
  - Non-existent user returns 401
"""
import pytest


def test_register_password_creates_user_and_returns_token(client, test_db):
    res = client.post(
        "/auth/register/password",
        json={
            "name": "New User",
            "email": "newuser@example.com",
            "phone": "9876543210",
            "password": "supersecret123",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["access_token"]
    assert body["expires_in_minutes"] == 15
    assert body["rep"]["primary_email"] == "newuser@example.com"
    assert body["rep"]["name"] == "New User"

    # Verify refresh cookie was set
    assert "refresh_token" in res.cookies


def test_login_password_success_returns_2fa_challenge(client, seeded_rep):
    """Reps now get 2FA on login — verify the challenge envelope."""
    res = client.post(
        "/auth/login/password",
        json={"identifier": "test.rep@syngenta.com", "password": "testpass123"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["requires_2fa"] is True
    assert body["challenge_id"]
    assert body["email_masked"].startswith("t")  # test.rep@... → t****@s******.com
    assert body["expires_in_seconds"] == 300
    # In DEV_MODE the code is returned for testability
    assert body["dev_otp"]
    assert len(body["dev_otp"]) == 6


def test_password_then_2fa_completes_login_with_cookie(client, seeded_rep):
    """End-to-end: password → 2FA challenge → verify → tokens issued."""
    # Step 1 — password
    login_res = client.post(
        "/auth/login/password",
        json={"identifier": "test.rep@syngenta.com", "password": "testpass123"},
    )
    assert login_res.status_code == 200
    challenge = login_res.json()

    # Step 2 — verify OTP
    verify_res = client.post(
        "/auth/2fa/verify",
        json={"challenge_id": challenge["challenge_id"], "code": challenge["dev_otp"]},
    )
    assert verify_res.status_code == 200, verify_res.text
    body = verify_res.json()
    assert body["access_token"]
    assert body["expires_in_minutes"] == 15
    assert body["rep"]["primary_email"] == "test.rep@syngenta.com"
    assert "refresh_token" in verify_res.cookies


def test_login_password_wrong_password_returns_401(client, seeded_rep):
    res = client.post(
        "/auth/login/password",
        json={"identifier": "test.rep@syngenta.com", "password": "WRONG_PASSWORD"},
    )
    assert res.status_code == 401
    assert "Invalid credentials" in res.json()["detail"]


def test_login_password_nonexistent_user_returns_401(client, test_db):
    res = client.post(
        "/auth/login/password",
        json={"identifier": "ghost@example.com", "password": "anything123"},
    )
    assert res.status_code == 401