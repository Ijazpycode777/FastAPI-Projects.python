"""Timetable service: create entries with backend-enforced conflict detection."""
from __future__ import annotations

from datetime import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.assignments import TeacherAssignment
from app.models.people import Teacher
from app.models.timetable import TimetableEntry, TimetablePeriod
from app.repositories.audit import record_audit
from app.services.timetable_conflict import EntryRef, conflict_reason, find_conflict


async def create_period(db: AsyncSession, actor, **kw) -> TimetablePeriod:
    obj = TimetablePeriod(**kw)
    db.add(obj)
    await db.flush()
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="timetable_period.create", resource_type="timetable_period", resource_id=obj.id)
    await db.commit()
    await db.refresh(obj)
    return obj


async def create_entry(db: AsyncSession, actor, data: dict[str, Any]) -> TimetableEntry:
    """Create a scheduled lecture with full conflict validation."""
    teacher = await db.get(Teacher, data["teacher_id"])
    if teacher is None:
        raise NotFoundError("Teacher not found.")

    # Authorization: the teacher must be assigned to this subject+class(+section).
    stmt = select(TeacherAssignment).where(
        TeacherAssignment.teacher_id == data["teacher_id"],
        TeacherAssignment.subject_id == data["subject_id"],
        TeacherAssignment.class_id == data["class_id"],
        TeacherAssignment.is_active.is_(True),
    )
    if data.get("section_id"):
        stmt = stmt.where(
            (TeacherAssignment.section_id == data["section_id"]) | (TeacherAssignment.section_id.is_(None))
        )
    if (await db.execute(stmt)).scalar_one_or_none() is None:
        raise ForbiddenError("Teacher is not assigned to this subject/class/section.")

    # Pull same-day candidates for conflict detection.
    candidates = await db.execute(
        select(TimetableEntry).where(
            TimetableEntry.academic_session_id == data["academic_session_id"],
            TimetableEntry.day_of_week == data["day_of_week"],
            TimetableEntry.is_cancelled.is_(False),
        )
    )
    existing = [
        EntryRef(
            id=str(e.id), day_of_week=e.day_of_week,
            start_time=e.start_time, end_time=e.end_time,
            teacher_id=str(e.teacher_id), classroom_id=str(e.classroom_id) if e.classroom_id else None,
            class_id=str(e.class_id), section_id=str(e.section_id) if e.section_id else None,
        )
        for e in candidates.scalars().all()
    ]
    new_ref = EntryRef(
        id="new", day_of_week=data["day_of_week"],
        start_time=data["start_time"], end_time=data["end_time"],
        teacher_id=data["teacher_id"],
        classroom_id=data.get("classroom_id"),
        class_id=data["class_id"], section_id=data.get("section_id"),
    )
    conflict = find_conflict(new_ref, existing)
    if conflict:
        raise ConflictError(conflict_reason(conflict, new_ref))

    entry = TimetableEntry(**data)
    db.add(entry)
    await db.flush()
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="timetable_entry.create", resource_type="timetable_entry", resource_id=entry.id,
                       after={"day": data["day_of_week"], "teacher": data["teacher_id"]})
    await db.commit()
    await db.refresh(entry)
    return entry


async def cancel_entry(db: AsyncSession, actor, entry: TimetableEntry) -> TimetableEntry:
    entry.is_cancelled = True
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="timetable_entry.cancel", resource_type="timetable_entry", resource_id=entry.id)
    await db.commit()
    await db.refresh(entry)
    return entry


async def weekly_for_teacher(db: AsyncSession, teacher_id: str) -> list[TimetableEntry]:
    result = await db.execute(
        select(TimetableEntry).where(
            TimetableEntry.teacher_id == teacher_id,
            TimetableEntry.is_cancelled.is_(False),
        ).order_by(TimetableEntry.day_of_week, TimetableEntry.start_time)
    )
    return list(result.scalars().all())


async def weekly_for_class(db: AsyncSession, class_id: str, section_id: str | None) -> list[TimetableEntry]:
    stmt = select(TimetableEntry).where(
        TimetableEntry.class_id == class_id,
        TimetableEntry.is_cancelled.is_(False),
    ).order_by(TimetableEntry.day_of_week, TimetableEntry.start_time)
    if section_id:
        stmt = stmt.where((TimetableEntry.section_id == section_id) | (TimetableEntry.section_id.is_(None)))
    return list((await db.execute(stmt)).scalars().all())
