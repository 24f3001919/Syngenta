import uuid
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from jose import JWTError
from datetime import datetime, timezone


from models.db.rep import Rep
from models.db.auth_identity import AuthIdentity
from models.db.refresh_token import RefreshToken
from models.schemas.auth import PasswordRegisterRequest
from core.auth.security import (
    hash_password,
    verify_password,
    normalize_phone,
    is_email,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from core.auth.email_otp.store import email_otp_store, Challenge
from core.auth.email_otp.sender import email_sender, resolve_destination, mask_email
from config import TWO_FA_REQUIRED_ROLES

class AuthService:
    # ---------- helpers ----------

    def _find_identity(self, db: Session, provider: str, identifier: str) -> Optional[AuthIdentity]:
        return (
            db.query(AuthIdentity)
            .filter(AuthIdentity.provider == provider, AuthIdentity.identifier == identifier)
            .first()
        )

    def _find_rep_by_email(self, db: Session, email: str) -> Optional[Rep]:
        return db.query(Rep).filter(Rep.primary_email == email.lower()).first()

    # ---------- password register / login ----------

    def register_with_password(self, db: Session, data: PasswordRegisterRequest) -> Rep:
        email = data.email.lower().strip()
        phone = normalize_phone(data.phone)
        if not phone:
            raise HTTPException(status_code=400, detail="Invalid phone number")

        if self._find_rep_by_email(db, email):
            raise HTTPException(status_code=409, detail="Email already registered")
        if self._find_identity(db, "password", email):
            raise HTTPException(status_code=409, detail="Email already registered")
        if self._find_identity(db, "whatsapp_otp", phone):
            raise HTTPException(status_code=409, detail="Phone already registered")

        rep = Rep(
            id=str(uuid.uuid4()),
            rep_id=data.rep_id,
            name=data.name.strip(),
            primary_email=email,
            role="rep",
            managed_rep_ids=[],
            is_active=True,
        )
        db.add(rep)
        db.flush()

        db.add(AuthIdentity(
            id=str(uuid.uuid4()),
            rep_id=rep.id,
            provider="password",
            identifier=email,
            credential=hash_password(data.password),
            verified_at=None,
        ))
        db.add(AuthIdentity(
            id=str(uuid.uuid4()),
            rep_id=rep.id,
            provider="whatsapp_otp",
            identifier=phone,
            credential=None,
            verified_at=None,
        ))
        db.commit()
        db.refresh(rep)
        return rep

    def login_with_password(self, db: Session, identifier: str, password: str) -> Rep:
        identifier = (identifier or "").strip()
        if not identifier:
            raise HTTPException(status_code=400, detail="Identifier required")

        if is_email(identifier):
            ident = self._find_identity(db, "password", identifier.lower())
        else:
            phone = normalize_phone(identifier)
            phone_ident = self._find_identity(db, "whatsapp_otp", phone)
            ident = None
            if phone_ident:
                ident = (
                    db.query(AuthIdentity)
                    .filter(
                        AuthIdentity.rep_id == phone_ident.rep_id,
                        AuthIdentity.provider == "password",
                    )
                    .first()
                )

        if not ident or not ident.credential or not verify_password(password, ident.credential):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        rep = db.query(Rep).filter(Rep.id == ident.rep_id).first()
        if not rep or not rep.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")
        return rep
    # ---------- 2FA email-OTP login ----------

    def role_requires_2fa(self, rep: Rep) -> bool:
        """Whether this rep's role is on the 2FA enforcement list."""
        return rep.role in TWO_FA_REQUIRED_ROLES

    def begin_2fa_login(self, db: Session, rep: Rep) -> tuple[Challenge, str, str]:
        """Issue a fresh OTP challenge for a rep who's just passed password auth.

        Returns (challenge, destination_email_used, masked_original_email).
        Caller (the route) is responsible for sending the email — this method
        only generates the challenge and dispatches via the email_sender.

        We send to `destination_email_used` (which may differ from rep email
        in demo mode) but always log the masked ORIGINAL email so judges /
        users know which account they're logging into.
        """
        if not rep.primary_email:
            raise HTTPException(
                status_code=400,
                detail="Account has no email on file — cannot send 2FA code.",
            )

        challenge = email_otp_store.issue(rep_id=rep.id, email=rep.primary_email)
        destination = resolve_destination(rep.primary_email)

        sent = email_sender.send(
            to=destination,
            code=challenge.code,
            original_email=rep.primary_email,
        )
        if not sent:
            # Don't leak the failure path to the client — but invalidate the
            # challenge so the user can't lock themselves out on a typo
            # against a code that was never sent.
            email_otp_store.invalidate(challenge.challenge_id)
            raise HTTPException(
                status_code=503,
                detail="Could not send verification code. Please try again shortly.",
            )

        masked = mask_email(rep.primary_email)
        return challenge, destination, masked

    def complete_2fa_login(
        self,
        db: Session,
        challenge_id: str,
        code: str,
    ) -> Rep:
        """Verify the OTP code against the challenge.

        On success → return the Rep (caller issues the token pair).
        On failure → raise 401. Either bad code, expired challenge,
        or attempts exhausted — same error message to avoid leaking which.
        """
        challenge = email_otp_store.verify(challenge_id, code)
        if not challenge:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired verification code.",
            )

        rep = db.query(Rep).filter(Rep.id == challenge.rep_id).first()
        if not rep or not rep.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")

        return rep

    # ---------- OTP login ----------

    def login_or_signup_with_phone(self, db: Session, phone: str) -> Rep:
        phone = normalize_phone(phone)
        if not phone:
            raise HTTPException(status_code=400, detail="Invalid phone number")

        ident = self._find_identity(db, "whatsapp_otp", phone)

        if ident:
            rep = db.query(Rep).filter(Rep.id == ident.rep_id).first()
            if not rep or not rep.is_active:
                raise HTTPException(status_code=403, detail="Account disabled")
            if not ident.verified_at:
                ident.verified_at = datetime.now(timezone.utc)
                db.commit()
            return rep

        rep = Rep(
            id=str(uuid.uuid4()),
            rep_id=None,
            name=f"User {phone[-4:]}",
            primary_email=None,
            role="rep",
            managed_rep_ids=[],
            is_active=True,
        )
        db.add(rep)
        db.flush()

        db.add(AuthIdentity(
            id=str(uuid.uuid4()),
            rep_id=rep.id,
            provider="whatsapp_otp",
            identifier=phone,
            credential=None,
            verified_at=datetime.now(timezone.utc),
        ))
        db.commit()
        db.refresh(rep)
        return rep

    # ---------- Google login ----------

    def login_or_signup_with_google(self, db: Session, info: Dict[str, Any]) -> Rep:
        google_sub = info["sub"]
        email      = info["email"].lower().strip()
        name       = info.get("name") or email.split("@")[0]

        ident = self._find_identity(db, "google", google_sub)
        if ident:
            rep = db.query(Rep).filter(Rep.id == ident.rep_id).first()
            if not rep or not rep.is_active:
                raise HTTPException(status_code=403, detail="Account disabled")
            return rep

        rep = self._find_rep_by_email(db, email)
        if rep:
            if not rep.is_active:
                raise HTTPException(status_code=403, detail="Account disabled")
            db.add(AuthIdentity(
                id=str(uuid.uuid4()),
                rep_id=rep.id,
                provider="google",
                identifier=google_sub,
                credential=None,
                verified_at=datetime.now(timezone.utc),
            ))
            db.commit()
            db.refresh(rep)
            return rep

        rep = Rep(
            id=str(uuid.uuid4()),
            rep_id=None,
            name=name,
            primary_email=email,
            role="rep",
            managed_rep_ids=[],
            is_active=True,
        )
        db.add(rep)
        db.flush()

        db.add(AuthIdentity(
            id=str(uuid.uuid4()),
            rep_id=rep.id,
            provider="google",
            identifier=google_sub,
            credential=None,
            verified_at=datetime.now(timezone.utc),
        ))
        db.commit()
        db.refresh(rep)
        return rep

    # ---------- linking ----------

    def link_google_to_current(self, db: Session, rep: Rep, info: Dict[str, Any]) -> Rep:
        google_sub = info["sub"]
        existing = self._find_identity(db, "google", google_sub)
        if existing:
            if existing.rep_id == rep.id:
                return rep
            raise HTTPException(
                status_code=409,
                detail="This Google account is already linked to a different user",
            )

        db.add(AuthIdentity(
            id=str(uuid.uuid4()),
            rep_id=rep.id,
            provider="google",
            identifier=google_sub,
            credential=None,
            verified_at=datetime.now(timezone.utc),
        ))
        db.commit()
        db.refresh(rep)
        return rep

    def link_phone_to_current(self, db: Session, rep: Rep, phone: str) -> Rep:
        phone = normalize_phone(phone)
        existing = self._find_identity(db, "whatsapp_otp", phone)
        if existing:
            if existing.rep_id == rep.id:
                if not existing.verified_at:
                    existing.verified_at = datetime.now(timezone.utc)
                    db.commit()
                return rep
            raise HTTPException(
                status_code=409,
                detail="This phone number is already linked to a different user",
            )

        db.add(AuthIdentity(
            id=str(uuid.uuid4()),
            rep_id=rep.id,
            provider="whatsapp_otp",
            identifier=phone,
            credential=None,
            verified_at=datetime.now(timezone.utc),
        ))
        db.commit()
        db.refresh(rep)
        return rep

    # ---------- seeding ----------

    def ensure_seed_rep(
        self,
        db: Session,
        *,
        rep_id: Optional[str],
        name: str,
        email: str,
        phone: Optional[str],
        password: str,
        role: str = "rep",
        managed_rep_ids: Optional[List[str]] = None,
    ) -> Rep:
        email = email.lower()
        phone = normalize_phone(phone) if phone else None

        rep = self._find_rep_by_email(db, email)
        if rep:
            return rep

        rep = Rep(
            id=str(uuid.uuid4()),
            rep_id=rep_id,
            name=name,
            primary_email=email,
            role=role,
            managed_rep_ids=managed_rep_ids or [],
            is_active=True,
        )
        db.add(rep)
        db.flush()

        db.add(AuthIdentity(
            id=str(uuid.uuid4()),
            rep_id=rep.id,
            provider="password",
            identifier=email,
            credential=hash_password(password),
            verified_at=datetime.now(timezone.utc),
        ))
        if phone:
            db.add(AuthIdentity(
                id=str(uuid.uuid4()),
                rep_id=rep.id,
                provider="whatsapp_otp",
                identifier=phone,
                credential=None,
                verified_at=datetime.now(timezone.utc),
            ))
        db.commit()
        db.refresh(rep)
        return rep
    # ---------- token pair issue / refresh / revoke ----------

    def issue_token_pair(
        self,
        db: Session,
        rep: Rep,
        *,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
        device_id: Optional[str] = None,
    ) -> Tuple[str, str, datetime]:
        """Create an access token + refresh token pair, persist the refresh jti.

        Returns (access_token, refresh_token, refresh_expires_at).
        The refresh token JWT is meant to go straight into an httpOnly cookie.
        """
        access = create_access_token(
            subject=rep.id,
            extra_claims={
                "rep_id": rep.rep_id,
                "email":  rep.primary_email,
                "role":   rep.role,
            },
        )

        refresh_jwt, jti, expires_at = create_refresh_token(subject=rep.id)

        db.add(RefreshToken(
            id=str(uuid.uuid4()),
            rep_id=rep.id,
            jti=jti,
            device_id=device_id,
            issued_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            revoked_at=None,
            user_agent=(user_agent or "")[:500] or None,
            ip_hash=self._hash_ip(ip) if ip else None,
        ))
        db.commit()
        return access, refresh_jwt, expires_at


    def rotate_refresh_token(
        self,
        db: Session,
        refresh_jwt: str,
        *,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> Tuple[Rep, str, str, datetime]:
        """Validate the presented refresh token, revoke it, and issue a new pair.

        Returns (rep, new_access_token, new_refresh_token, new_refresh_expires_at).
        Raises 401 if the token is invalid, expired, revoked, or reused after rotation.
        """
        if not refresh_jwt:
            raise HTTPException(status_code=401, detail="Missing refresh token")

        try:
            payload = decode_refresh_token(refresh_jwt)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        rep_pk = payload.get("sub")
        jti    = payload.get("jti")
        if not rep_pk or not jti:
            raise HTTPException(status_code=401, detail="Malformed refresh token")

        # Look up DB row
        record: Optional[RefreshToken] = (
            db.query(RefreshToken)
            .filter(RefreshToken.jti == jti)
            .first()
        )
        if not record:
            # Token signature valid but not in DB → never issued or wiped.
            raise HTTPException(status_code=401, detail="Refresh token not recognised")

        # Reuse detection: if it was already revoked due to rotation, someone replayed it.
        # Nuke all sessions for this rep — they're compromised.
        if record.revoked_at is not None:
            self._revoke_all_for_rep(db, record.rep_id, reason="reuse_detected")
            raise HTTPException(status_code=401, detail="Refresh token reuse detected; all sessions revoked")

        if record.is_expired:
            raise HTTPException(status_code=401, detail="Refresh token expired")

        rep = db.query(Rep).filter(Rep.id == record.rep_id).first()
        if not rep or not rep.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")

        # Mark old token as rotated, issue new pair
        record.revoked_at = datetime.now(timezone.utc)
        record.revoked_reason = "rotated"

        access, new_refresh, new_expires = self.issue_token_pair(
            db,
            rep,
            user_agent=user_agent,
            ip=ip,
            device_id=record.device_id,
        )

        # Wire the rotation chain so audit shows old → new
        # (We need the new jti — pull from DB by fetching the just-inserted row)
        latest = (
            db.query(RefreshToken)
            .filter(RefreshToken.rep_id == rep.id)
            .order_by(RefreshToken.issued_at.desc())
            .first()
        )
        if latest:
            record.replaced_by_jti = latest.jti
        db.commit()

        return rep, access, new_refresh, new_expires


    def revoke_refresh_token(
        self,
        db: Session,
        refresh_jwt: Optional[str],
        *,
        reason: str = "logout",
    ) -> None:
        """Revoke a single refresh token. Silent on invalid/missing input (logout
        should always 'succeed' from the user's perspective)."""
        if not refresh_jwt:
            return
        try:
            payload = decode_refresh_token(refresh_jwt)
        except JWTError:
            return
        jti = payload.get("jti")
        if not jti:
            return
        record = db.query(RefreshToken).filter(RefreshToken.jti == jti).first()
        if record and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            record.revoked_reason = reason
            db.commit()


    def _revoke_all_for_rep(self, db: Session, rep_pk: str, *, reason: str) -> int:
        """Revoke every active refresh token for a rep. Used on reuse detection."""
        now = datetime.now(timezone.utc)
        rows = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.rep_id == rep_pk,
                RefreshToken.revoked_at.is_(None),
            )
            .all()
        )
        for r in rows:
            r.revoked_at = now
            r.revoked_reason = reason
        db.commit()
        return len(rows)


    @staticmethod
    def _hash_ip(ip: str) -> str:
        """SHA-256 a client IP for forensic correlation without storing raw IP."""
        return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32]