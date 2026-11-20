"""Student management: create, update, deactivate, promote, board records."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.academic import AcademicSession, ClassLevel, Program, Section
from app.models.people import (
    BoardExaminationRecord,
    Guardian,
    Student,
    StudentAcademicHistory,
    StudentEnrolment,
)
from app.models.user import User
from app.repositories.audit import record_audit, snapshot
from app.security.password import hash_password
from app.services.grading import percentage_for
from app.utils.helpers import admission_number_year_prefix, next_roll_number


async def _validate_placement(db: AsyncSession, program_id: str, class_id: str, section_id: str, session_id: str) -> None:
    cls = await db.get(ClassLevel, class_id)
    if cls is None or cls.program_id != program_id:
        raise ValidationError("Class does not belong to the given program.")
    sec = await db.get(Section, section_id)
    if sec is None or sec.class_level_id != class_id:
        raise ValidationError("Section does not belong to the given class.")
    sess = await db.get(AcademicSession, session_id)
    if sess is None:
        raise ValidationError("Academic session not found.")


async def _next_admission_number(db: AsyncSession, admitted_on: date) -> str:
    prefix = admission_number_year_prefix(admitted_on)
    count = (await db.execute(select(func.count()).select_from(Student))).scalar_one()
    return f"{prefix}-{count + 1:05d}"


async def _next_roll_number_for_section(db: AsyncSession, session_id: str, section_id: str) -> int:
    result = await db.execute(
        select(StudentEnrolment.roll_number).where(
            StudentEnrolment.academic_session_id == session_id,
            StudentEnrolment.section_id == section_id,
        )
    )
    return next_roll_number([r for r in result.scalars().all()])


async def create_student(db: AsyncSession, actor: User, data: dict[str, Any]) -> Student:
    """Create a user + student + enrolment + optional board records in one transaction."""
    from app.security.password import is_strong_password

    ok, reason = is_strong_password(data["password"])
    if not ok:
        raise ValidationError(reason or "Weak password.")

    email = data["email"].lower().strip()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ConflictError("A user with that email already exists.")

    await _validate_placement(db, data["program_id"], data["class_id"], data["section_id"], data["academic_session_id"])

    # Optional board record cross-field validation.
    for level in ("matric", "inter"):
        total = data.get(f"{level}_total")
        obtained = data.get(f"{level}_obtained")
        if (total is not None) ^ (obtained is not None):
            raise ValidationError(f"{level} total and obtained must both be provided.")
        if total is not None and obtained is not None and obtained > total:
            raise ValidationError(f"{level} obtained cannot exceed total.")

    user = User(
        email=email,
        role="student",
        password_hash=hash_password(data["password"]),
        full_name=data["full_name"],
        phone=data.get("phone"),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    guardian = None
    if data.get("guardian"):
        g = data["guardian"]
        guardian = Guardian(
            name=g["name"],
            phone=g["phone"],
            email=g.get("email"),
            relationship_type=g.get("relationship_type", "Guardian"),
            occupation=g.get("occupation"),
        )
        db.add(guardian)
        await db.flush()

    roll = await _next_roll_number_for_section(db, data["academic_session_id"], data["section_id"])
    admission_no = await _next_admission_number(db, data["admission_date"])

    student = Student(
        user_id=user.id,
        admission_number=admission_no,
        full_name=data["full_name"],
        email=email,
        phone=data.get("phone"),
        date_of_birth=data.get("date_of_birth"),
        gender=data.get("gender"),
        guardian_id=guardian.id if guardian else None,
        admission_date=data["admission_date"],
        account_status="active",
        current_program_id=data["program_id"],
        current_class_id=data["class_id"],
        current_section_id=data["section_id"],
        current_session_id=data["academic_session_id"],
        current_roll_number=roll,
    )
    db.add(student)
    await db.flush()

    enrolment = StudentEnrolment(
        student_id=student.id,
        academic_session_id=data["academic_session_id"],
        program_id=data["program_id"],
        class_id=data["class_id"],
        section_id=data["section_id"],
        roll_number=roll,
        is_active=True,
    )
    db.add(enrolment)
    await db.flush()

    # Board records
    if data.get("matric_total") is not None:
        pct = percentage_for(data["matric_obtained"], data["matric_total"])
        db.add(BoardExaminationRecord(
            student_id=student.id, level="matric", board=data["matric_board"],
            examination_year=data["matric_year"], total_marks=data["matric_total"],
            obtained_marks=data["matric_obtained"], grade=data.get("matric_grade"),
        ))
    if data.get("inter_total") is not None:
        db.add(BoardExaminationRecord(
            student_id=student.id, level="inter_part1", board=data["inter_board"],
            examination_year=data["inter_year"], total_marks=data["inter_total"],
            obtained_marks=data["inter_obtained"], grade=data.get("inter_grade"),
        ))

    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="student.create", resource_type="student", resource_id=student.id,
        after={"admission_number": admission_no, "email": email},
    )
    await db.commit()
    await db.refresh(student)
    return student


async def update_student(db: AsyncSession, actor: User, student: Student, data: dict[str, Any]) -> Student:
    before = await snapshot(student)
    for k, v in data.items():
        if v is not None:
            setattr(student, k, v)
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="student.update", resource_type="student", resource_id=student.id,
        before=before, after=await snapshot(student),
    )
    await db.commit()
    await db.refresh(student)
    return student


async def toggle_active(db: AsyncSession, actor: User, student: Student, active: bool) -> Student:
    before = await snapshot(student)
    student.account_status = "active" if active else "inactive"
    # Update the linked user account explicitly. We must NOT touch
    # ``student.user`` here — that relationship is lazy and the Student was
    # loaded by a plain ``db.get`` in the route, so navigating it under async
    # would trigger a synchronous lazy load (MissingGreenlet on asyncpg).
    await db.execute(update(User).where(User.id == student.user_id).values(is_active=active))
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action=f"student.{'activate' if active else 'deactivate'}",
        resource_type="student", resource_id=student.id,
        before=before, after=await snapshot(student),
    )
    await db.commit()
    await db.refresh(student)
    return student


async def promote(db: AsyncSession, actor: User, data: dict[str, Any]) -> Student:
    """Promote / repeat / change section. Preserves history; never overwrites."""
    student = await db.get(Student, data["student_id"])
    if student is None:
        raise NotFoundError("Student not found.")

    await _validate_placement(
        db,
        data.get("new_program_id") or student.current_program_id,
        data["new_class_id"],
        data["new_section_id"],
        data["new_academic_session_id"],
    )

    # Deactivate the previous enrolment (keep the row).
    prev_active = await db.execute(
        select(StudentEnrolment).where(
            StudentEnrolment.student_id == student.id,
            StudentEnrolment.is_active.is_(True),
        )
    )
    prev_enrolment = prev_active.scalar_one_or_none()

    before = await snapshot(student)
    prev_class = prev_enrolment.class_id if prev_enrolment else None
    prev_section = prev_enrolment.section_id if prev_enrolment else None
    prev_session = prev_enrolment.academic_session_id if prev_enrolment else None
    prev_roll = prev_enrolment.roll_number if prev_enrolment else None

    if prev_enrolment:
        prev_enrolment.is_active = False

    new_roll = await _next_roll_number_for_section(db, data["new_academic_session_id"], data["new_section_id"])
    new_enrolment = StudentEnrolment(
        student_id=student.id,
        academic_session_id=data["new_academic_session_id"],
        program_id=data.get("new_program_id") or student.current_program_id,
        class_id=data["new_class_id"],
        section_id=data["new_section_id"],
        roll_number=new_roll,
        is_active=True,
    )
    db.add(new_enrolment)
    await db.flush()

    history = StudentAcademicHistory(
        student_id=student.id,
        enrolment_id=new_enrolment.id,
        previous_class=prev_class,
        previous_section=prev_section,
        previous_session=prev_session,
        previous_roll_number=prev_roll,
        action=data["action"],
        note=data.get("note"),
    )
    db.add(history)

    student.current_program_id = new_enrolment.program_id
    student.current_class_id = new_enrolment.class_id
    student.current_section_id = new_enrolment.section_id
    student.current_session_id = new_enrolment.academic_session_id
    student.current_roll_number = new_roll

    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action=f"student.{data['action']}", resource_type="student", resource_id=student.id,
        before=before, after=await snapshot(student),
    )
    await db.commit()
    await db.refresh(student)
    return student
