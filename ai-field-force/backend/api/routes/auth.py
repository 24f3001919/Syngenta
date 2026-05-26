# backend/api/routes/auth.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Request, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from db.session import get_db
from models.db.rep import Rep
from models.schemas.auth import (
    PasswordRegisterRequest,
    PasswordLoginRequest,
    TokenResponse,
    RepProfile,
    Login2FAResponse,
    Verify2FARequest,
    VerifyEmailRequest,
)
from models.schemas.otp import (
    OtpSendRequest,
    OtpSendResponse,
    OtpVerifyRequest,
)
from models.schemas.google import GoogleVerifyRequest
from services.auth_service import AuthService
from core.auth.security import normalize_phone
from core.auth.dependencies import get_current_rep
from core.auth.otp.store import otp_store
from core.auth.otp.factory import otp_sender
from core.auth.google_verify import verify_google_id_token
from config import (
    JWT_ACCESS_EXPIRE_MINUTES,
    JWT_REFRESH_EXPIRE_DAYS,
    OTP_EXPIRY_SECONDS,
    OTP_EMAIL_EXPIRY_SECONDS,
    DEV_MODE,
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_DOMAIN,
    REFRESH_COOKIE_SECURE,
    REFRESH_COOKIE_SAMESITE,
)

router = APIRouter()
service = AuthService()


# ─── Cookie helpers ───────────────────────────────────────────────────────────

def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set the httpOnly refresh cookie. Environment controls Secure/SameSite."""
    kwargs = {
        "key":      REFRESH_COOKIE_NAME,
        "value":    refresh_token,
        "httponly": True,
        "secure":   REFRESH_COOKIE_SECURE,
        "samesite": REFRESH_COOKIE_SAMESITE,
        "max_age":  JWT_REFRESH_EXPIRE_DAYS * 24 * 3600,
        "path":     "/auth",   # cookie only sent to /auth/* endpoints
    }
    if REFRESH_COOKIE_DOMAIN:
        kwargs["domain"] = REFRESH_COOKIE_DOMAIN
    response.set_cookie(**kwargs)


def _clear_refresh_cookie(response: Response) -> None:
    kwargs = {
        "key":    REFRESH_COOKIE_NAME,
        "path":   "/auth",
    }
    if REFRESH_COOKIE_DOMAIN:
        kwargs["domain"] = REFRESH_COOKIE_DOMAIN
    response.delete_cookie(**kwargs)


def _client_context(request: Request) -> dict:
    """Pull user-agent + client IP for token record. Best-effort, never fails."""
    ua = request.headers.get("user-agent", "")
    # Respect X-Forwarded-For if present (Render sets this)
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "")
    return {"user_agent": ua, "ip": ip}


def _issue_and_set(
    response: Response,
    request: Request,
    db: Session,
    rep: Rep,
) -> TokenResponse:
    """Issue access+refresh pair, set cookie, return response body."""
    ctx = _client_context(request)
    access, refresh, _ = service.issue_token_pair(
        db, rep,
        user_agent=ctx["user_agent"],
        ip=ctx["ip"],
    )
    _set_refresh_cookie(response, refresh)
    return TokenResponse(
        access_token=access,
        expires_in_minutes=JWT_ACCESS_EXPIRE_MINUTES,
        rep=RepProfile.model_validate(rep),
    )


# ─── Password ─────────────────────────────────────────────────────────────────

@router.post("/register/password", response_model=TokenResponse, status_code=201,
             summary="Register with email + password")
def register_password(
    data: PasswordRegisterRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    rep = service.register_with_password(db, data)
    return _issue_and_set(response, request, db, rep)


@router.post("/login/password",
             summary="Login with email or phone + password (may return 2FA challenge)")
def login_password(
    data: PasswordLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Two-stage password login:
      1. Validate credentials
      2. If user's role requires 2FA → send OTP, return Login2FAResponse
         Frontend then POSTs to /auth/2fa/verify to complete login
      3. If role does not require 2FA → issue token pair directly (legacy path)

    Response shape varies — frontend must check the `requires_2fa` field.
    """
    rep = service.login_with_password(db, data.identifier, data.password)

    if not service.role_requires_2fa(rep):
        # Legacy single-factor path (e.g. for service accounts or test reps)
        return _issue_and_set(response, request, db, rep)

    # 2FA branch — send OTP and return challenge
    challenge, destination, masked = service.begin_2fa_login(db, rep)
    return Login2FAResponse(
        requires_2fa=True,
        challenge_id=challenge.challenge_id,
        email_masked=masked,
        expires_in_seconds=OTP_EMAIL_EXPIRY_SECONDS,
        dev_otp=challenge.code if DEV_MODE else None,
    )


@router.post("/token", response_model=TokenResponse,
             summary="OAuth2 form-data login (for Swagger Authorize button)")
def login_form(
    response: Response,
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    rep = service.login_with_password(db, form.username, form.password)
    return _issue_and_set(response, request, db, rep)


# ─── OTP login ────────────────────────────────────────────────────────────────

@router.post("/otp/send", response_model=OtpSendResponse,
             summary="Send a one-time code to a phone number")
def otp_send(data: OtpSendRequest):
    phone = normalize_phone(data.phone)
    if not phone or len(phone) < 7:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    code = otp_store.issue(phone)
    otp_sender.send(phone, code)

    return OtpSendResponse(
        phone=phone,
        expires_in_seconds=OTP_EXPIRY_SECONDS,
        sent_via=otp_sender.name,
        dev_otp=code if DEV_MODE else None,
    )


@router.post("/otp/verify", response_model=TokenResponse,
             summary="Verify the OTP and log in (auto-creates account if new)")
def otp_verify(
    data: OtpVerifyRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    phone = normalize_phone(data.phone)
    otp_store.verify(phone, data.code)
    rep = service.login_or_signup_with_phone(db, phone)
    return _issue_and_set(response, request, db, rep)


# ─── Google login ─────────────────────────────────────────────────────────────

@router.post("/google/verify", response_model=TokenResponse,
             summary="Verify a Google id_token and log in (auto-creates / auto-links)")
def google_verify(
    data: GoogleVerifyRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    info = verify_google_id_token(data.id_token)
    rep = service.login_or_signup_with_google(db, info)
    return _issue_and_set(response, request, db, rep)


# ─── Refresh + Logout (NEW) ───────────────────────────────────────────────────
@router.post("/2fa/verify", response_model=TokenResponse,
             summary="Complete 2FA login by verifying the email OTP")
def verify_2fa(
    data: Verify2FARequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Complete the password+2FA login flow.

    Frontend gets a `challenge_id` from /auth/login/password and submits it
    here along with the 6-digit code from the user's email. On success,
    issues the standard access + refresh token pair.
    """
    rep = service.complete_2fa_login(db, data.challenge_id, data.code)
    return _issue_and_set(response, request, db, rep)

@router.post("/refresh", response_model=TokenResponse,
             summary="Rotate the refresh token (cookie) for a fresh access token")
def refresh_tokens(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    refresh_token: Optional[str] = Cookie(None, alias=REFRESH_COOKIE_NAME),
):
    """
    Reads the refresh token from the httpOnly cookie, validates + rotates it,
    and returns a new access token in the body. The new refresh token is
    written back to the same httpOnly cookie.
    """
    ctx = _client_context(request)
    rep, access, new_refresh, _ = service.rotate_refresh_token(
        db,
        refresh_token,
        user_agent=ctx["user_agent"],
        ip=ctx["ip"],
    )
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(
        access_token=access,
        expires_in_minutes=JWT_ACCESS_EXPIRE_MINUTES,
        rep=RepProfile.model_validate(rep),
    )


@router.post("/logout", status_code=200,
             summary="Revoke the current refresh token and clear the cookie")
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: Optional[str] = Cookie(None, alias=REFRESH_COOKIE_NAME),
):
    """Idempotent: always 200, even if no token was present."""
    service.revoke_refresh_token(db, refresh_token, reason="logout")
    _clear_refresh_cookie(response)
    return {"status": "ok"}


# ─── Account linking (requires auth) ──────────────────────────────────────────

@router.post("/link/google", response_model=RepProfile,
             summary="Link a Google account to the currently logged-in rep")
def link_google(
    data: GoogleVerifyRequest,
    db: Session = Depends(get_db),
    current: Rep = Depends(get_current_rep),
):
    info = verify_google_id_token(data.id_token)
    rep = service.link_google_to_current(db, current, info)
    return RepProfile.model_validate(rep)


@router.post("/link/phone/send", response_model=OtpSendResponse,
             summary="Send an OTP to a phone the user wants to link to their account")
def link_phone_send(
    data: OtpSendRequest,
    current: Rep = Depends(get_current_rep),
):
    phone = normalize_phone(data.phone)
    if not phone or len(phone) < 7:
        raise HTTPException(status_code=400, detail="Invalid phone number")

    code = otp_store.issue(phone)
    otp_sender.send(phone, code)

    return OtpSendResponse(
        phone=phone,
        expires_in_seconds=OTP_EXPIRY_SECONDS,
        sent_via=otp_sender.name,
        dev_otp=code if DEV_MODE else None,
    )


@router.post("/link/phone/verify", response_model=RepProfile,
             summary="Verify the OTP and attach the phone to the current account")
def link_phone_verify(
    data: OtpVerifyRequest,
    db: Session = Depends(get_db),
    current: Rep = Depends(get_current_rep),
):
    phone = normalize_phone(data.phone)
    otp_store.verify(phone, data.code)
    rep = service.link_phone_to_current(db, current, phone)
    return RepProfile.model_validate(rep)

# ─── Email verification ────────────────────────────────────────────────────────

@router.post("/verify-email", response_model=RepProfile,
             summary="Consume a verification token and mark the email as verified")
def verify_email(
    data: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    """
    Public endpoint — no auth required (the token IS the credential).
    Frontend hits this on /verify-email?token=... page load.
    Returns the full rep profile with email_verified_at now populated.
    Raises 400 if the token is invalid, already used, or expired.
    """
    identity = service.verify_email_token(db, data.token)
    rep = db.query(Rep).filter(Rep.id == identity.rep_id).first()
    if not rep:
        raise HTTPException(status_code=404, detail="Account not found")
    return RepProfile.model_validate(rep)


@router.post("/resend-verification", status_code=200,
             summary="Re-send the verification email for the current rep")
def resend_verification(
    db: Session = Depends(get_db),
    current: Rep = Depends(get_current_rep),
):
    """
    Auth-required. No-ops silently if already verified (returns 200 either way
    so the frontend doesn't need to special-case it).
    """
    sent = service.send_verification_email_for_user(db, current)
    if not sent:
        raise HTTPException(
            status_code=503,
            detail="Could not send verification email. Please try again shortly.",
        )
    return {"status": "ok", "message": "Verification email sent"}


# ─── Profile ──────────────────────────────────────────────────────────────────

@router.get("/me", response_model=RepProfile)
def me(current: Rep = Depends(get_current_rep)):
    return RepProfile.model_validate(current)