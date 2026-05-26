"""
EmailVerification — one-time tokenised link for email address confirmation.

Token is never stored in plain form; only a SHA-256 hex digest is persisted.
The plain token is returned once at issuance time and embedded in the email
link. 24-hour expiry is intentionally longer than 2FA OTPs because users
click links at their own pace, not in a live login flow.
"""
import hashlib
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship

from db.session import Base


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id               = Column(String, primary_key=True)                                              # uuid
    auth_identity_id = Column(
        String, ForeignKey("auth_identities.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    token_hash       = Column(String, nullable=False, unique=True)                                   # sha256 hex of plain token
    expires_at       = Column(DateTime, nullable=False)
    used_at          = Column(DateTime, nullable=True)                                               # NULL = still valid
    created_at       = Column(DateTime, default=datetime.utcnow)

    identity = relationship("AuthIdentity", backref="verification_tokens")

    # ── convenience ──────────────────────────────────────────────────────────

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @staticmethod
    def hash_token(plain: str) -> str:
        return hashlib.sha256(plain.encode()).hexdigest()