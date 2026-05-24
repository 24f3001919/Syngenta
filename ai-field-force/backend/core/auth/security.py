import re
import secrets
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    JWT_ACCESS_EXPIRE_MINUTES,
    JWT_REFRESH_EXPIRE_DAYS,
    JWT_REFRESH_SECRET,
)

# ---------- passwords ----------
_BCRYPT_MAX_BYTES = 72


def _truncate(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_truncate(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_truncate(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------- access tokens (short-lived, sent in Authorization header) ----------

def create_access_token(subject: str, extra_claims: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=JWT_ACCESS_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "typ": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    # Defense in depth: reject refresh tokens used as access tokens
    if payload.get("typ") not in (None, "access"):
        raise JWTError("Not an access token")
    return payload


# ---------- refresh tokens (long-lived, sent in httpOnly cookie) ----------

def create_refresh_token(subject: str, jti: Optional[str] = None) -> tuple[str, str, datetime]:
    """Create a refresh token. Returns (token, jti, expires_at).

    The jti (JWT ID) is also stored in DB so we can revoke individual tokens
    without invalidating every refresh token issued to this user.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=JWT_REFRESH_EXPIRE_DAYS)
    jti = jti or secrets.token_urlsafe(16)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "typ": "refresh",
        "jti": jti,
    }
    token = jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)
    return token, jti, expire


def decode_refresh_token(token: str) -> dict:
    """Decode + validate a refresh token. Raises JWTError on any mismatch."""
    payload = jwt.decode(token, JWT_REFRESH_SECRET, algorithms=[JWT_ALGORITHM])
    if payload.get("typ") != "refresh":
        raise JWTError("Not a refresh token")
    if not payload.get("jti") or not payload.get("sub"):
        raise JWTError("Refresh token missing claims")
    return payload


# ---------- identifier helpers ----------

def normalize_phone(raw: str) -> str:
    return re.sub(r"\D", "", raw or "")


def is_email(identifier: str) -> bool:
    return "@" in (identifier or "")