"""Examination service: create, enter marks, publish, finalize (versioned grading)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models.academic import ClassLevel, Section, Subject
from app.models.examinations import Examination, GradingBoundary, GradingPolicy, StudentMark
from app.models.people import StudentEnrolment
from app.repositories.audit import record_audit
from app.services.academic_service import teacher_authorized_for
from app.services.exam_marks import MarkInput, MarksError, compute_mark_result, validate_mark
from app.services.grading import Boundary


async def _load_boundaries(db: AsyncSession, policy_id: str | None) -> list[Boundary]:
    """Explicitly load a grading policy's boundaries as plain Boundary values.

    We deliberately avoid accessing the ``GradingPolicy.boundaries`` relationship
    here. Under async SQLAlchemy that relationship is only populated when it is
    eagerly loaded as part of a query that returned the parent; if the policy
    instance is already in the session's identity map (e.g. it was just created
    and flushed earlier in the same transaction, as happens during seeding),
    ``db.get`` returns the cached instance without re-running the selectin
    loader, and reading ``.boundaries`` would then trigger a synchronous lazy
    load — raising ``MissingGreenlet`` on asyncpg. An explicit query sidesteps
    the relationship entirely and is safe on every backend.
    """
    if not policy_id:
        return []
    rows = (await db.execute(
        select(GradingBoundary)
        .where(GradingBoundary.policy_id == policy_id)
        .order_by(GradingBoundary.min_percentage)
    )).scalars().all()
    return [
        Boundary(r.grade_name, float(r.min_percentage), float(r.max_percentage), bool(r.is_pass), r.description)
        for r in rows
    ]


async def assert_teacher_can_manage_exam(db: AsyncSession, actor, exam: Examination) -> None:
    """Authorize a teacher to manage an exam (enter/publish/finalize/view marks).

    Admins bypass. Teachers must be currently assigned to the exam's subject +
    class (+ section). The exam's creator is NOT specially exempted: if a
    teacher is unassigned from the subject/class they lose access, which is the
    intended permission boundary (no lingering rights after unassignment).
    """
    if actor.role == "admin":
        return
    if actor.role != "teacher":
        raise ForbiddenError("Only staff can manage examinations.")
    teacher_id = str(actor.teacher_profile.id) if getattr(actor, "teacher_profile", None) else None
    if not teacher_id:
        raise ForbiddenError("Teacher profile not found.")
    auth = await teacher_authorized_for(
        db, teacher_id, str(exam.subject_id), str(exam.class_id),
        str(exam.section_id) if exam.section_id else None,
    )
    if not auth:
        raise ForbiddenError("You are not authorized to manage this examination.")


async def create_exam(db: AsyncSession, actor, data: dict[str, Any]) -> Examination:
    policy_id = data.get("grading_policy_id")
    if policy_id:
        policy = await db.get(GradingPolicy, policy_id)
        if policy is None:
            raise NotFoundError("Grading policy not found.")

    # D4: validate the exam's academic structure is internally consistent. The
    # examination table carries redundant FKs (program_id is reachable via
    # class_id; section_id via class_id) kept for query convenience — they must
    # not be allowed to disagree, or reports joining on the redundant column
    # would silently produce wrong results.
    cls = await db.get(ClassLevel, data["class_id"])
    if cls is None:
        raise NotFoundError("Class not found.")
    if str(cls.program_id) != str(data["program_id"]):
        raise ValidationError("The selected class does not belong to the selected program.")
    subj = await db.get(Subject, data["subject_id"])
    if subj is None:
        raise NotFoundError("Subject not found.")
    if str(subj.program_id) != str(data["program_id"]):
        raise ValidationError("The selected subject does not belong to the selected program.")
    if data.get("section_id"):
        sec = await db.get(Section, data["section_id"])
        if sec is None:
            raise NotFoundError("Section not found.")
        if str(sec.class_level_id) != str(data["class_id"]):
            raise ValidationError("The selected section does not belong to the selected class.")

    if actor.role == "teacher":
        auth = await teacher_authorized_for(
            db, str(actor.teacher_profile.id), data["subject_id"], data["class_id"],
            data.get("section_id"),
        )
        if not auth:
            raise ForbiddenError("You are not authorized to create exams for this subject/class.")
    exam = Examination(
        name=data["name"], exam_type=data["exam_type"],
        academic_session_id=data["academic_session_id"], program_id=data["program_id"],
        class_id=data["class_id"], section_id=data.get("section_id"),
        subject_id=data["subject_id"], max_marks=data["max_marks"],
        passing_marks=data["passing_marks"], exam_date=data["exam_date"],
        status="draft", created_by=actor.id, grading_policy_id=policy_id,
    )
    db.add(exam)
    await db.flush()
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="exam.create", resource_type="examination", resource_id=exam.id)
    await db.commit()
    await db.refresh(exam)
    return exam


async def enter_marks(db: AsyncSession, actor, teacher_id: str, data: dict[str, Any]) -> list[StudentMark]:
    exam = await db.get(Examination, data["examination_id"])
    if exam is None:
        raise NotFoundError("Examination not found.")
    if exam.status == "finalized":
        raise ForbiddenError("Examination is finalized; marks cannot be changed.")
    await assert_teacher_can_manage_exam(db, actor, exam)

    boundaries = await _load_boundaries(db, exam.grading_policy_id)

    created: list[StudentMark] = []
    now_dt = datetime.now(timezone.utc)  # D7: native timezone-aware DateTime
    for entry in data["entries"]:
        try:
            validate_mark(entry["marks_obtained"], exam.max_marks, entry.get("is_absent", False))
            result = compute_mark_result(
                MarkInput(entry["student_id"], float(entry["marks_obtained"]), entry.get("is_absent", False)),
                max_marks=exam.max_marks, passing_marks=exam.passing_marks, boundaries=boundaries,
            )
        except MarksError as exc:
            raise ValidationError(str(exc))
        # D4: the student must be actively enrolled in the exam's academic session
        # and belong to the exam's class (and section, if the exam is
        # section-specific). Without this a mark could be recorded for a student
        # in a completely different class.
        enrol = await db.execute(select(StudentEnrolment).where(
            StudentEnrolment.student_id == entry["student_id"],
            StudentEnrolment.academic_session_id == str(exam.academic_session_id),
            StudentEnrolment.is_active.is_(True),
        ))
        enr = enrol.scalar_one_or_none()
        if enr is None:
            raise ValidationError(
                f"Student {entry['student_id']} is not enrolled in this exam's academic session.")
        if str(enr.class_id) != str(exam.class_id):
            raise ValidationError(
                f"Student {entry['student_id']} does not belong to this exam's class.")
        if exam.section_id is not None and str(enr.section_id) != str(exam.section_id):
            raise ValidationError(
                f"Student {entry['student_id']} does not belong to this exam's section.")
        # upsert: replace existing mark row for this exam+student
        existing = await db.execute(select(StudentMark).where(
            StudentMark.examination_id == exam.id, StudentMark.student_id == entry["student_id"],
        ))
        mark = existing.scalar_one_or_none()
        if mark is None:
            mark = StudentMark(
                examination_id=exam.id, student_id=entry["student_id"], subject_id=str(exam.subject_id),
                recorded_by=actor.id, recorded_at=now_dt,
            )
            db.add(mark)
        mark.marks_obtained = result.marks_obtained
        mark.is_absent = result.is_absent
        mark.percentage = result.percentage
        mark.grade = result.grade
        mark.is_pass = result.is_pass
        mark.status = "entered"
        mark.note = entry.get("note")
        created.append(mark)
    await db.flush()
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="exam.enter_marks", resource_type="examination", resource_id=exam.id,
                       after={"count": len(created)})
    await db.commit()
    for m in created:
        await db.refresh(m)
    return created


async def publish(db: AsyncSession, actor, exam: Examination) -> Examination:
    await assert_teacher_can_manage_exam(db, actor, exam)
    if exam.status == "finalized":
        raise ConflictError("Examination is already finalized.")
    exam.status = "published"
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="exam.publish", resource_type="examination", resource_id=exam.id)
    await db.commit()
    await db.refresh(exam)
    return exam


async def finalize(db: AsyncSession, actor, exam: Examination) -> Examination:
    """Freeze results. Captures the grading policy version used."""
    await assert_teacher_can_manage_exam(db, actor, exam)
    if exam.grading_policy_id is None:
        raise ValidationError("Examination has no grading policy; cannot finalize.")
    now_dt = datetime.now(timezone.utc)  # D7: native timezone-aware DateTime
    exam.status = "finalized"
    exam.finalized_by = actor.id
    exam.finalized_at = now_dt
    marks = await db.execute(select(StudentMark).where(StudentMark.examination_id == exam.id))
    for m in marks.scalars().all():
        m.status = "finalized"
        m.finalized_at = now_dt
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="exam.finalize", resource_type="examination", resource_id=exam.id,
                       after={"status": "finalized", "policy_id": str(exam.grading_policy_id)})
    await db.commit()
    await db.refresh(exam)
    return exam
