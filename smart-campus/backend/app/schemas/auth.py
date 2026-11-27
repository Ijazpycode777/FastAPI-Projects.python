"""Auth & user schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMBase


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequestIn(BaseModel):
    email: EmailStr


class PasswordResetConfirmIn(BaseModel):
    token: str
    new_password: str = Field(min_length=10, max_length=128)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class AdminCreateIn(BaseModel):
    """An admin creates another admin account. The new admin is active and can
    log in immediately with the chosen password (no forced reset — the creating
    admin handed over the credential deliberately)."""
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=160)
    phone: str | None = None
    password: str = Field(min_length=10, max_length=128)


class CsrfOut(BaseModel):
    csrf_token: str


class UserOut(ORMBase):
    id: str
    email: str
    role: str
    full_name: str
    phone: str | None = None
    is_active: bool
    must_reset_password: bool
    last_login_at: datetime | None = None


class ProfileOut(BaseModel):
    user: UserOut
    # Role-specific profile (teacher / student) — set when applicable
    teacher: dict | None = None
    student: dict | None = None


class LoginOut(ProfileOut):
    """Login response: the user profile PLUS the freshly rotated CSRF token.

    The backend rotates the CSRF cookie on login (session-fixation protection),
    so the in-memory token the frontend fetched via /auth/csrf before login is
    now stale relative to the cookie. Returning the new token here lets the
    frontend sync its in-memory copy immediately -- otherwise the first
    state-changing request after login sends a stale token, 403s, and depends
    on the api.ts refresh+retry path (which can surface a misleading
    'session expired' 401 if the refresh call is blocked or rate-limited)."""
    csrf_token: str


class ResetPasswordOut(BaseModel):
    temporary_password: str
    message: str
