# backend/models/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field, model_validator
from datetime import datetime
from typing import Optional, List, Literal


class PasswordRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    email: EmailStr
    phone: str = Field(..., min_length=7, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)
    rep_id: Optional[str] = None


class PasswordLoginRequest(BaseModel):
    identifier: str = Field(..., description="Email or phone number")
    password: str


class LinkedIdentity(BaseModel):
    provider: Literal["password", "whatsapp_otp", "google"]
    identifier: str
    verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RepProfile(BaseModel):
    id: str
    rep_id: Optional[str] = None
    name: str
    primary_email: Optional[EmailStr] = None
    role: str
    managed_rep_ids: List[str] = []
    is_active: bool
    created_at: datetime
    identities: List[LinkedIdentity] = []
    email_verified_at: Optional[datetime] = None  # derived from password AuthIdentity.verified_at

    @model_validator(mode="after")
    def _derive_email_verified_at(self) -> "RepProfile":
        """Populate email_verified_at from the password identity if not set explicitly."""
        if self.email_verified_at is None:
            for ident in self.identities:
                if ident.provider == "password":
                    self.email_verified_at = ident.verified_at
                    break
        return self

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    rep: RepProfile


RegisterRequest = PasswordRegisterRequest
LoginRequest = PasswordLoginRequest
class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=200)


class Login2FAResponse(BaseModel):    
    """Returned by /auth/login/password when 2FA is required.

    The frontend uses challenge_id to call /auth/2fa/verify with the code.
    `dev_otp` is only populated in DEV_MODE to make demo logins frictionless.
    """
    requires_2fa: bool = True
    challenge_id: str
    email_masked: str
    expires_in_seconds: int
    dev_otp: Optional[str] = None


class Verify2FARequest(BaseModel):
    challenge_id: str
    code: str = Field(..., min_length=4, max_length=10)