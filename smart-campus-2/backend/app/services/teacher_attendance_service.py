"""Teacher self-attendance service: check-in / check-out with server timestamps."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.attendance import TeacherAttendance
from app.models.people import Teacher
from app.repositories.audit import record_audit
from app.services.teacher_attendance_logic import (
    can_check_in,
    can_check_out,
    compute_late_status,
    compute_work_minutes,
    finalize_status,
    parse_work_start,
)


async def _today_record(db: AsyncSession, teacher_id: str, on: date) -> TeacherAttendance | None:
    result = await db.execute(
        select(TeacherAttendance).where(
            TeacherAttendance.teacher_id == teacher_id,
            TeacherAttendance.attendance_date == on,
        )
    )
    return result.scalar_one_or_none()


async def check_in(db: AsyncSession, actor, teacher_id: str) -> TeacherAttendance:
    teacher = await db.get(Teacher, teacher_id)
    if teacher is None:
        raise NotFoundError("Teacher not found.")
    if str(teacher.user_id) != str(actor.id) and actor.role != "admin":
        raise ValidationError("You can only check in for yourself.")

    now = datetime.now(timezone.utc)
    today = now.date()
    record = await _today_record(db, teacher_id, today)
    if not can_check_in(record.check_in_at if record else None):
        raise ConflictError("You have already checked in today.")
    if record is None:
        record = TeacherAttendance(
            teacher_id=teacher_id,
            attendance_date=today,
            check_in_at=now,
            status="present",
            work_minutes=0,
        )
        db.add(record)
    else:
        record.check_in_at = now

    work_start = parse_work_start(settings.teacher_work_start)
    record.status = compute_late_status(now, work_start, settings.teacher_late_threshold_minutes)

    await db.flush()
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="teacher_attendance.check_in", resource_type="teacher_attendance",
                       resource_id=record.id, after={"check_in_at": now.isoformat()})
    await db.commit()
    await db.refresh(record)
    return record


async def check_out(db: AsyncSession, actor, teacher_id: str) -> TeacherAttendance:
    now = datetime.now(timezone.utc)
    today = now.date()
    record = await _today_record(db, teacher_id, today)
    if record is None or not can_check_out(record.check_in_at, record.check_out_at):
        raise ConflictError("No active check-in to check out from.")
    record.check_out_at = now
    record.work_minutes = compute_work_minutes(record.check_in_at, now)
    record.status = finalize_status(record.check_in_at, record.check_out_at)
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="teacher_attendance.check_out", resource_type="teacher_attendance",
                       resource_id=record.id, after={"check_out_at": now.isoformat(),
                                                      "work_minutes": record.work_minutes})
    await db.commit()
    await db.refresh(record)
    return record


async def monthly_summary(db: AsyncSession, teacher_id: str, year: int, month: int) -> dict[str, Any]:
    result = await db.execute(
        select(TeacherAttendance).where(
            TeacherAttendance.teacher_id == teacher_id,
            func.extract("year", TeacherAttendance.attendance_date) == year,
            func.extract("month", TeacherAttendance.attendance_date) == month,
        )
    )
    rows = list(result.scalars().all())
    present = sum(1 for r in rows if r.status == "present")
    late = sum(1 for r in rows if r.status == "late")
    absent = sum(1 for r in rows if r.status == "absent")
    total_min = sum(r.work_minutes for r in rows)
    return {
        "teacher_id": teacher_id,
        "days_present": present,
        "days_late": late,
        "days_absent": absent,
        "total_working_minutes": total_min,
        "late_arrivals": late,
    }
