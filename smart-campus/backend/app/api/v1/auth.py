"""Authentication & account endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.limiter import rate_limit
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AdminCreateIn,
    CsrfOut,
    LoginIn,
    LoginOut,
    PasswordChangeIn,
    ProfileOut,
    ResetPasswordOut,
    UserOut,
)
from app.security.dependencies import get_current_user, require_admin
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/csrf", response_model=CsrfOut)
async def get_csrf(request: Request, response: Response):
    """Issue a CSRF token cookie. Safe to call before login."""
    token = await auth_service.issue_csrf(response, request, None)
    return CsrfOut(csrf_token=token)


@router.post("/login", response_model=LoginOut)
@rate_limit(lambda: settings.login_rate_limit)
async def login(payload: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    user, csrf = await auth_service.login(db, request, response, payload.email, payload.password)
    # Return the rotated CSRF token so the frontend can sync its in-memory copy
    # (login rotates the cookie; without this the first mutation sends a stale
    # token and 403s).
    profile = _profile(user)
    return LoginOut(**profile.model_dump(), csrf_token=csrf)


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
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.change_password(db, request, user, payload.current_password, payload.new_password)
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


@router.get("/admins", response_model=list[UserOut], dependencies=[Depends(require_admin())])
async def list_admins(admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    """List all administrator accounts (for the Administrators management page)."""
    return await auth_service.list_admins(db)


@router.post("/admins", response_model=UserOut, status_code=201, dependencies=[Depends(require_admin())])
async def create_admin(
    payload: AdminCreateIn,
    request: Request,
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    """An admin creates another admin account. The new admin is active immediately."""
    user = await auth_service.create_admin(db, admin, request, payload.model_dump())
    return UserOut.model_validate(user)


def _profile(user: User) -> ProfileOut:
    teacher = None
    student = None
    if user.teacher_profile is not None:
        t = user.teacher_profile
        teacher = {
            "id": str(t.id),
            "employee_id": t.employee_id,
            "department_id": str(t.department_id),
            "department_name": t.department_name,
            "subject": t.subject,
        }
    if user.student_profile is not None:
        s = user.student_profile
        student = {"id": str(s.id), "admission_number": s.admission_number}
    return ProfileOut(user=UserOut.model_validate(user), teacher=teacher, student=student)
