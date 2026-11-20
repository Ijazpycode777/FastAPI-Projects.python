"""Leave records for students and teachers. Admin-submitted only.

Leave is stored as a distinct record (never a fake attendance row). The
submitting administrator is recorded in ``approved_by`` and the record is
created with ``status='approved'``.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.attendance import LeaveRecord
from app.models.people import Student, Teacher
from app.repositories.audit import record_audit


async def create_leave(db: AsyncSession, actor, data: dict[str, Any]) -> LeaveRecord:
    person_type = data["person_type"]
    if person_type == "student":
        if await db.get(Student, data["student_id"]) is None:
            raise NotFoundError("Student not found.")
    else:
        if await db.get(Teacher, data["teacher_id"]) is None:
            raise NotFoundError("Teacher not found.")

    rec = LeaveRecord(
        person_type=person_type,
        student_id=data["student_id"] if person_type == "student" else None,
        teacher_id=data["teacher_id"] if person_type == "teacher" else None,
        start_date=data["start_date"],
        end_date=data["end_date"],
        reason=data["reason"],
        status="approved",
        approved_by=actor.id,
    )
    db.add(rec)
    await db.flush()
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="leave.create", resource_type="leave_record", resource_id=rec.id,
        after={"person_type": person_type, "start": str(data["start_date"]),
               "end": str(data["end_date"]), "reason": data["reason"]},
    )
    await db.commit()
    await db.refresh(rec)
    return rec


async def list_leaves(
    db: AsyncSession, person_type: str | None = None, person_id: str | None = None
) -> list[LeaveRecord]:
    stmt = select(LeaveRecord)
    if person_type:
        stmt = stmt.where(LeaveRecord.person_type == person_type)
    if person_id and person_type == "student":
        stmt = stmt.where(LeaveRecord.student_id == person_id)
    elif person_id and person_type == "teacher":
        stmt = stmt.where(LeaveRecord.teacher_id == person_id)
    stmt = stmt.order_by(LeaveRecord.start_date.desc())
    return list((await db.execute(stmt)).scalars().all())
