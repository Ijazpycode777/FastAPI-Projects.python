"""Leave record routes — admin submission + listing for students and teachers."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.schemas.attendance import LeaveIn, LeaveOut
from app.security.dependencies import require_admin
from app.services import leave_service

router = APIRouter(prefix="/leave", tags=["leave"])


@router.post("", response_model=LeaveOut, dependencies=[Depends(require_admin())])
async def create_leave(
    payload: LeaveIn,
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    rec = await leave_service.create_leave(db, admin, payload.model_dump())
    return LeaveOut.model_validate(rec)


@router.get("", response_model=list[LeaveOut], dependencies=[Depends(require_admin())])
async def list_leaves(
    person_type: str | None = Query(None, pattern="^(student|teacher)$"),
    person_id: str | None = Query(None),
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    rows = await leave_service.list_leaves(db, person_type, person_id)
    return [LeaveOut.model_validate(r) for r in rows]


@router.get("/student/{student_id}", response_model=list[LeaveOut], dependencies=[Depends(require_admin())])
async def student_leaves(
    student_id: str,
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    rows = await leave_service.list_leaves(db, "student", student_id)
    return [LeaveOut.model_validate(r) for r in rows]


@router.get("/teacher/{teacher_id}", response_model=list[LeaveOut], dependencies=[Depends(require_admin())])
async def teacher_leaves(
    teacher_id: str,
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    rows = await leave_service.list_leaves(db, "teacher", teacher_id)
    return [LeaveOut.model_validate(r) for r in rows]
