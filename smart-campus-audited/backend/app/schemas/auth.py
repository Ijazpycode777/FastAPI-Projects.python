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
    last_login_at: str | None = None


class ProfileOut(BaseModel):
    user: UserOut
    # Role-specific profile (teacher / student) — set when applicable
    teacher: dict | None = None
    student: dict | None = None


class ResetPasswordOut(BaseModel):
    temporary_password: str
    message: str
