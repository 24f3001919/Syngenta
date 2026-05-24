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


@router.post("/login/password", response_model=TokenResponse,
             summary="Login with email or phone + password")
def login_password(
    data: PasswordLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
):
    rep = service.login_with_password(db, data.identifier, data.password)
    return _issue_and_set(response, request, db, rep)


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


# ─── Profile ──────────────────────────────────────────────────────────────────

@router.get("/me", response_model=RepProfile)
def me(current: Rep = Depends(get_current_rep)):
    return RepProfile.model_validate(current)