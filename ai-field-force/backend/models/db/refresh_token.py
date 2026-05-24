# backend/models/db/refresh_token.py
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from db.session import Base


class RefreshToken(Base):
    """A long-lived refresh token tied to one Rep + optional device.

    Stored server-side so we can:
      - Revoke individual sessions (logout one device but keep others alive)
      - Detect token reuse after rotation (security signal: someone has a stolen token)
      - Show users their active sessions

    The JWT itself is sent to the client as an httpOnly cookie. We store
    only the `jti` (JWT ID) here — never the raw token — so a DB leak
    doesn't immediately yield usable credentials.
    """
    __tablename__ = "refresh_tokens"

    id          = Column(String, primary_key=True)                                        # uuid
    rep_id      = Column(String, ForeignKey("reps.id", ondelete="CASCADE"), index=True)   # FK to Rep.id (uuid PK)
    jti         = Column(String, unique=True, index=True, nullable=False)                 # JWT ID claim
    device_id   = Column(String, nullable=True, index=True)                               # optional device association
    issued_at   = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at  = Column(DateTime, nullable=False, index=True)
    revoked_at  = Column(DateTime, nullable=True)                                         # when revoked (logout / rotation)
    revoked_reason = Column(String, nullable=True)                                        # "logout" | "rotated" | "reuse_detected" | "admin"
    replaced_by_jti = Column(String, nullable=True)                                       # forward pointer for rotation chain
    user_agent  = Column(String, nullable=True)                                           # snapshot at issue time
    ip_hash     = Column(String, nullable=True)                                           # hashed IP for forensics (never raw)

    rep = relationship("Rep")

    __table_args__ = (
        Index("ix_refresh_active", "rep_id", "revoked_at"),
    )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.is_revoked and not self.is_expired