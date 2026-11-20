"""Teacher self-attendance routes (check-in / check-out)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.attendance import TeacherAttendance
from app.models.user import User
from app.schemas.attendance import TeacherAttendanceOut, TeacherAttendanceSummary
from app.security.dependencies import require_teacher
from app.services import teacher_attendance_service

router = APIRouter(prefix="/teacher-attendance", tags=["teacher-attendance"])


@router.post("/check-in", response_model=TeacherAttendanceOut)
async def check_in(user: User = Depends(require_teacher()), db: AsyncSession = Depends(get_db)):
    rec = await teacher_attendance_service.check_in(db, user, str(user.teacher_profile.id))
    return TeacherAttendanceOut.model_validate(rec)


@router.post("/check-out", response_model=TeacherAttendanceOut)
async def check_out(user: User = Depends(require_teacher()), db: AsyncSession = Depends(get_db)):
    rec = await teacher_attendance_service.check_out(db, user, str(user.teacher_profile.id))
    return TeacherAttendanceOut.model_validate(rec)


@router.get("/today", response_model=TeacherAttendanceOut | None)
async def today(user: User = Depends(require_teacher()), db: AsyncSession = Depends(get_db)):
    from datetime import date as _date
    result = await db.execute(select(TeacherAttendance).where(
        TeacherAttendance.teacher_id == str(user.teacher_profile.id),
        TeacherAttendance.attendance_date == _date.today(),
    ))
    rec = result.scalar_one_or_none()
    return TeacherAttendanceOut.model_validate(rec) if rec else None


@router.get("/history", response_model=list[TeacherAttendanceOut])
async def history(user: User = Depends(require_teacher()), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(TeacherAttendance).where(
        TeacherAttendance.teacher_id == str(user.teacher_profile.id)
    ).order_by(TeacherAttendance.attendance_date.desc()).limit(90))
    return [TeacherAttendanceOut.model_validate(r) for r in rows.scalars().all()]


@router.get("/summary", response_model=TeacherAttendanceSummary)
async def summary(year: int = Query(None), month: int = Query(None), user: User = Depends(require_teacher()), db: AsyncSession = Depends(get_db)):
    from datetime import date as _date
    today = _date.today()
    return TeacherAttendanceSummary.model_validate(
        await teacher_attendance_service.monthly_summary(db, str(user.teacher_profile.id), year or today.year, month or today.month)
    )
