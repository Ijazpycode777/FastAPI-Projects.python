"""Role-specific dashboard aggregates."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.security.dependencies import get_current_user, require_admin, require_student, require_teacher
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/admin", dependencies=[Depends(require_admin())])
async def admin_dashboard(db: AsyncSession = Depends(get_db)):
    return await dashboard_service.admin_dashboard(db)


@router.get("/teacher")
async def teacher_dashboard(user: User = Depends(require_teacher()), db: AsyncSession = Depends(get_db)):
    return await dashboard_service.teacher_dashboard(db, user)


@router.get("/student")
async def student_dashboard(user: User = Depends(require_student()), db: AsyncSession = Depends(get_db)):
    return await dashboard_service.student_dashboard(db, user)


@router.get("/me")
async def my_dashboard(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "admin":
        return await dashboard_service.admin_dashboard(db)
    if user.role == "teacher":
        return await dashboard_service.teacher_dashboard(db, user)
    return await dashboard_service.student_dashboard(db, user)
