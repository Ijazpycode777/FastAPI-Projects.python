"""Student attendance routes."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.database.session import get_db
from app.models.attendance import AttendanceRecord
from app.models.user import User
from app.schemas.attendance import (
    AttendanceBulkIn,
    AttendanceOut,
    AttendanceUpdateIn,
)
from app.security.dependencies import get_current_user, require_admin, require_staff, require_student
from app.services import attendance_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/mark", response_model=list[AttendanceOut], dependencies=[Depends(require_staff())])
async def mark(payload: AttendanceBulkIn, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    if user.role != "teacher":
        raise ForbiddenError("Only teachers can mark attendance.")
    records = await attendance_service.mark_bulk(db, user, str(user.teacher_profile.id), payload.model_dump())
    return [AttendanceOut.model_validate(r) for r in records]


@router.patch("/{record_id}", response_model=AttendanceOut, dependencies=[Depends(require_staff())])
async def update_record(record_id: str, payload: AttendanceUpdateIn, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    record = await db.get(AttendanceRecord, record_id)
    if record is None:
        raise NotFoundError("Attendance record not found.")
    admin = user.role == "admin"
    if not admin and str(record.teacher_id) != str(user.teacher_profile.id):
        raise ForbiddenError("You can only update your own attendance records.")
    record = await attendance_service.update_one(db, user, record, payload.status, payload.note, admin)
    return AttendanceOut.model_validate(record)


@router.get("/student/{student_id}")
async def student_attendance(student_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "student" and str(user.student_profile.id) != str(student_id):
        raise ForbiddenError("You can only view your own attendance.")
    return await attendance_service.student_percentage(db, student_id)


@router.get("/student/{student_id}/breakdown")
async def student_breakdown(student_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Present/Absent/Leave donut data for a student (admin or self)."""
    if user.role == "student" and str(user.student_profile.id) != str(student_id):
        raise ForbiddenError("You can only view your own attendance.")
    return await attendance_service.student_breakdown(db, student_id)


@router.get("/me/breakdown", dependencies=[Depends(require_student())])
async def my_breakdown(user: User = Depends(require_student()), db: AsyncSession = Depends(get_db)):
    return await attendance_service.student_breakdown(db, str(user.student_profile.id))


@router.get("/class/{class_id}")
async def class_attendance(
    class_id: str,
    section_id: str | None = Query(None),
    on: date | None = Query(None),
    user: User = Depends(require_staff()),
    db: AsyncSession = Depends(get_db),
):
    return await attendance_service.class_summary(db, class_id, section_id, on)


@router.get("/records", response_model=list[AttendanceOut])
async def list_records(
    student_id: str | None = Query(None),
    timetable_entry_id: str | None = Query(None),
    on: date | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AttendanceRecord)
    if student_id:
        stmt = stmt.where(AttendanceRecord.student_id == student_id)
    if timetable_entry_id:
        stmt = stmt.where(AttendanceRecord.timetable_entry_id == timetable_entry_id)
    if on:
        stmt = stmt.where(AttendanceRecord.attendance_date == on)
    if user.role == "teacher":
        stmt = stmt.where(AttendanceRecord.teacher_id == str(user.teacher_profile.id))
    elif user.role == "student":
        stmt = stmt.where(AttendanceRecord.student_id == str(user.student_profile.id))
    rows = (await db.execute(stmt.order_by(AttendanceRecord.attendance_date.desc()).limit(200))).scalars().all()
    return [AttendanceOut.model_validate(r) for r in rows]
