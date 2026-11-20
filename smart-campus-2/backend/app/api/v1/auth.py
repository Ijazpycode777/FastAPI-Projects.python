"""Authentication & account endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import (
    CsrfOut,
    LoginIn,
    PasswordChangeIn,
    ProfileOut,
    ResetPasswordOut,
    UserOut,
)
from app.security.dependencies import get_current_user, require_admin
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/csrf", response_model=CsrfOut)
async def get_csrf(response: Response):
    """Issue a CSRF token cookie. Safe to call before login."""
    token = await auth_service.issue_csrf(response, None)
    return CsrfOut(csrf_token=token)


@router.post("/login", response_model=ProfileOut)
async def login(payload: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user, csrf = await auth_service.login(db, request, response, payload.email, payload.password)
    return _profile(user)


@router.post("/logout")
async def logout(request: Request, response: Response, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await auth_service.logout(db, request, response, user)
    return {"message": "Logged out."}


@router.get("/me", response_model=ProfileOut)
async def me(user: User = Depends(get_current_user)):
    return _profile(user)


@router.post("/password", response_model=dict)
async def change_password(
    payload: PasswordChangeIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.change_password(db, user, payload.current_password, payload.new_password)
    return {"message": "Password changed."}


@router.post("/reset/{user_id}", response_model=ResetPasswordOut)
async def admin_reset(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    target = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if target is None:
        raise NotFoundError("User not found.")
    temp = await auth_service.admin_reset_password(db, target, request)
    return ResetPasswordOut(temporary_password=temp, message="Temporary password issued. User must reset on next login.")


def _profile(user: User) -> ProfileOut:
    teacher = None
    student = None
    if user.teacher_profile is not None:
        t = user.teacher_profile
        teacher = {"id": str(t.id), "employee_id": t.employee_id, "department": t.department}
    if user.student_profile is not None:
        s = user.student_profile
        student = {"id": str(s.id), "admission_number": s.admission_number}
    return ProfileOut(user=UserOut.model_validate(user), teacher=teacher, student=student)
