"""Student attendance service: mark, update, summaries. Enforces authorization."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.academic import AcademicSession
from app.models.attendance import AttendanceRecord, Holiday, LeaveRecord
from app.models.people import Student, StudentEnrolment
from app.models.timetable import TimetableEntry
from app.repositories.audit import record_audit
from app.services.academic_service import teacher_authorized_for
from app.services.attendance_logic import attendance_percentage, count_statuses, is_valid_status

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


async def _resolve_enrolment(db: AsyncSession, student_id: str, session_id: str) -> StudentEnrolment:
    result = await db.execute(
        select(StudentEnrolment).where(
            StudentEnrolment.student_id == student_id,
            StudentEnrolment.academic_session_id == session_id,
            StudentEnrolment.is_active.is_(True),
        )
    )
    enrol = result.scalar_one_or_none()
    if enrol is None:
        raise NotFoundError("Student is not enrolled in this academic session.")
    return enrol


async def mark_bulk(
    db: AsyncSession, actor, teacher_id: str, data: dict[str, Any]
) -> list[AttendanceRecord]:
    """Mark attendance for a scheduled lecture. Rejects duplicates & unauthorized."""
    entry: TimetableEntry | None = await db.get(TimetableEntry, data["timetable_entry_id"])
    if entry is None or entry.is_cancelled:
        raise NotFoundError("Scheduled lecture not found.")
    if str(entry.teacher_id) != str(teacher_id):
        raise ForbiddenError("You can only mark attendance for your own scheduled lectures.")
    if data["attendance_date"].weekday() != ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"].index(entry.day_of_week):
        raise ValidationError("Attendance date does not match the lecture's day of week.")

    auth = await teacher_authorized_for(
        db, teacher_id, str(entry.subject_id), str(entry.class_id),
        str(entry.section_id) if entry.section_id else None,
        str(entry.academic_session_id),
    )
    if not auth:
        raise ForbiddenError("You are not authorized for this subject/class.")

    # Validate each mark and check duplicate prevention.
    seen_students: set[str] = set()
    for m in data["marks"]:
        if not is_valid_status(m["status"]):
            raise ValidationError(f"Invalid attendance status: {m['status']}.")
        if m["student_id"] in seen_students:
            raise ValidationError("Duplicate student in attendance payload.")
        seen_students.add(m["student_id"])

    now = datetime.now(timezone.utc)
    created: list[AttendanceRecord] = []
    for m in data["marks"]:
        enrol = await _resolve_enrolment(db, m["student_id"], str(entry.academic_session_id))
        if str(enrol.class_id) != str(entry.class_id):
            raise ForbiddenError("Student does not belong to this class.")
        existing = await db.execute(select(AttendanceRecord).where(
            AttendanceRecord.student_id == m["student_id"],
            AttendanceRecord.timetable_entry_id == entry.id,
            AttendanceRecord.attendance_date == data["attendance_date"],
        ))
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"Attendance already exists for student {m['student_id']} on {data['attendance_date']}."
            )
        rec = AttendanceRecord(
            student_id=m["student_id"],
            timetable_entry_id=entry.id,
            subject_id=str(entry.subject_id),
            teacher_id=teacher_id,
            class_id=str(entry.class_id),
            section_id=str(entry.section_id) if entry.section_id else None,
            academic_session_id=str(entry.academic_session_id),
            attendance_date=data["attendance_date"],
            status=m["status"],
            marked_by=actor.id,
            marked_at=now,
            is_finalized=False,
            note=data.get("note"),
        )
        db.add(rec)
        created.append(rec)

    await db.flush()
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="attendance.mark", resource_type="attendance_record",
        resource_id=str(entry.id),
        after={"date": str(data["attendance_date"]), "count": len(created)},
    )
    await db.commit()
    for r in created:
        await db.refresh(r)
    return created


async def update_one(
    db: AsyncSession, actor, record: AttendanceRecord, status: str, note: str | None, admin: bool
) -> AttendanceRecord:
    from app.services.attendance_logic import is_valid_status
    if not is_valid_status(status):
        raise ValidationError(f"Invalid attendance status: {status}.")
    if record.is_finalized and not admin:
        raise ForbiddenError("Attendance is finalized; only an administrator may correct it.")
    before_status = record.status
    record.status = status
    record.note = note
    record.is_finalized = admin  # admin corrections are flagged finalized
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="attendance.update", resource_type="attendance_record", resource_id=record.id,
        before={"status": before_status}, after={"status": status},
    )
    await db.commit()
    await db.refresh(record)
    return record


async def student_percentage(db: AsyncSession, student_id: str) -> dict[str, Any]:
    result = await db.execute(
        select(AttendanceRecord.status).where(AttendanceRecord.student_id == student_id)
    )
    statuses = [r for r in result.scalars().all()]
    c = count_statuses(statuses)
    pct = attendance_percentage(statuses)
    return {
        "student_id": student_id,
        "present": c.present,
        "absent": c.absent,
        "late": c.late,
        "excused": c.excused,
        "total_eligible": c.total_eligible,
        "percentage": pct,
    }


async def student_breakdown(
    db: AsyncSession, student_id: str, session_id: str | None = None
) -> dict[str, Any]:
    """Present / Absent / Leave donut data from real records + leave periods.

    - ``present`` = attendance records with status present or late
    - ``absent``  = attendance records with status absent
    - ``leave``   = scheduled sessions (timetable entry x date) that fall inside
      an approved leave period and have no present/absent record
    - ``total_scheduled`` = present + absent + leave
    - ``percentage`` = present / total_scheduled * 100

    Legacy ``excused`` records are preserved in the raw history but are not
    collapsed into any of these three segments (spec: do not convert excused
    into leave).
    """
    student = await db.get(Student, student_id)
    if student is None:
        raise NotFoundError("Student not found.")

    # Resolve the active enrolment (class/section/session).
    enrol_res = await db.execute(
        select(StudentEnrolment).where(
            StudentEnrolment.student_id == student_id,
            StudentEnrolment.is_active.is_(True),
        )
    )
    enrol = enrol_res.scalar_one_or_none()
    class_id = enrol.class_id if enrol else student.current_class_id
    section_id = enrol.section_id if enrol else student.current_section_id
    sess_id = session_id or (enrol.academic_session_id if enrol else student.current_session_id)
    if not (class_id and sess_id):
        return {"student_id": student_id, "present": 0, "absent": 0, "leave": 0,
                "total_scheduled": 0, "percentage": 0.0}

    # Attendance records for the student in this session.
    rec_rows = (await db.execute(
        select(AttendanceRecord.status, AttendanceRecord.timetable_entry_id, AttendanceRecord.attendance_date)
        .where(AttendanceRecord.student_id == student_id,
               AttendanceRecord.academic_session_id == sess_id)
    )).all()
    present = sum(1 for s, _, _ in rec_rows if s in ("present", "late"))
    absent = sum(1 for s, _, _ in rec_rows if s == "absent")
    marked = {(str(eid), d) for s, eid, d in rec_rows if s in ("present", "late", "absent")}

    # Timetable entries for the class/section in this session.
    ent_rows = (await db.execute(
        select(TimetableEntry).where(
            TimetableEntry.class_id == class_id,
            TimetableEntry.academic_session_id == sess_id,
            TimetableEntry.is_cancelled.is_(False),
        )
    )).scalars().all()
    if section_id:
        ent_rows = [e for e in ent_rows if e.section_id is None or str(e.section_id) == str(section_id)]

    # Approved leave periods for the student.
    leaves = (await db.execute(
        select(LeaveRecord).where(
            LeaveRecord.person_type == "student",
            LeaveRecord.student_id == student_id,
            LeaveRecord.status == "approved",
        )
    )).scalars().all()

    leave = 0
    session = await db.get(AcademicSession, sess_id)
    if session and ent_rows and leaves:
        holidays = {h.date for h in (await db.execute(
            select(Holiday).where(Holiday.academic_session_id == sess_id)
        )).scalars().all()}
        for lv in leaves:
            d = lv.start_date
            # cap iterations so a pathological range can never hang the request
            for _ in range(366 * 3):
                if d > lv.end_date:
                    break
                if session.start_date <= d <= session.end_date and d not in holidays:
                    wd = _WEEKDAYS[d.weekday()]
                    for e in ent_rows:
                        if e.day_of_week == wd and (str(e.id), d) not in marked:
                            leave += 1
                d += timedelta(days=1)

    total = present + absent + leave
    pct = round((present / total) * 100, 2) if total else 0.0
    return {
        "student_id": student_id, "present": present, "absent": absent,
        "leave": leave, "total_scheduled": total, "percentage": pct,
    }


async def class_summary(db: AsyncSession, class_id: str, section_id: str | None, on: date | None = None) -> list[dict[str, Any]]:
    """Per-student percentage for a class (optionally up to a date)."""
    stmt = select(AttendanceRecord).where(AttendanceRecord.class_id == class_id)
    if section_id:
        stmt = stmt.where((AttendanceRecord.section_id == section_id) | (AttendanceRecord.section_id.is_(None)))
    if on:
        stmt = stmt.where(AttendanceRecord.attendance_date <= on)
    rows = (await db.execute(stmt)).scalars().all()
    by_student: dict[str, list[str]] = {}
    for r in rows:
        by_student.setdefault(str(r.student_id), []).append(r.status)
    return [
        {"student_id": sid, "percentage": attendance_percentage(sts)}
        for sid, sts in by_student.items()
    ]
