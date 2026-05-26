"""
Email-verification token store — DB-backed (unlike the in-memory OTP store).

Tokens are 32-byte url-safe strings (secrets.token_urlsafe).
Only the SHA-256 hex digest is persisted; the plain token is returned once
at issuance and embedded in the verification link email.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models.db.auth_identity import AuthIdentity
from models.db.email_verification import EmailVerification

TOKEN_EXPIRY_HOURS = 24


def issue(
    db: Session,
    auth_identity_id: str,
) -> tuple[str, EmailVerification]:
    """Generate a fresh verification token, persist its hash, return plain token.

    The plain token must be embedded in the email link — it is never stored.
    Calling this again for the same identity is fine; old tokens stay in the DB
    and can still be used until they expire or are consumed.
    """
    plain = secrets.token_urlsafe(32)
    token_hash = EmailVerification.hash_token(plain)
    expires_at = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)

    record = EmailVerification(
        id=str(uuid.uuid4()),
        auth_identity_id=auth_identity_id,
        token_hash=token_hash,
        expires_at=expires_at,
        used_at=None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return plain, record


def verify(db: Session, token_plain: str) -> Optional[AuthIdentity]:
    """Look up the token, validate it, mark used, return the linked AuthIdentity.

    Returns None if the token is unknown, already used, or expired.
    On success sets used_at=now AND sets verified_at=now on the linked identity.
    """
    token_hash = EmailVerification.hash_token(token_plain)

    record: Optional[EmailVerification] = (
        db.query(EmailVerification)
        .filter(EmailVerification.token_hash == token_hash)
        .first()
    )

    if not record:
        return None
    if record.is_used:
        return None
    if record.is_expired:
        return None

    # Mark token consumed
    record.used_at = datetime.utcnow()

    # Mark identity verified
    identity: Optional[AuthIdentity] = (
        db.query(AuthIdentity)
        .filter(AuthIdentity.id == record.auth_identity_id)
        .first()
    )
    if not identity:
        db.commit()
        return None

    identity.verified_at = datetime.utcnow()
    db.commit()
    db.refresh(identity)
    return identity