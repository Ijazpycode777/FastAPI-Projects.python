"""Student management: create, update, deactivate, promote, board records."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select, update
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


# ----------------------------------------------------------------------------
# Free-text placement helpers.
#
# The admin types placement as free text (program / class / section / session
# NAMES, like a username). These helpers resolve a typed value to an existing
# row (matched case-insensitively by name, trimmed) or create it on the fly.
# They only ``flush`` — never ``commit`` — so a failed student create rolls
# back any auto-created academic rows too (the whole create_student call is one
# transaction).
# ----------------------------------------------------------------------------
_SESSION_RANGE_RE = re.compile(r"(\d{4})\s*[-–/]\s*(\d{2,4})")
_SESSION_YEAR_RE = re.compile(r"(\d{4})")


def _derive_session_dates(name: str) -> tuple[date, date]:
    """Best-effort start/end dates for a session created from a free-text name.

    '2025-2026' or '2025-26' -> Aug 1 2025 .. May 31 2026
    '2025'                   -> Aug 1 2025 .. May 31 2026
    anything else            -> Aug 1 (this year) .. May 31 (next year)
    """
    m = _SESSION_RANGE_RE.search(name)
    if m:
        y1 = int(m.group(1))
        y2 = int(m.group(2))
        if len(m.group(2)) <= 2:
            century = (y1 // 100) * 100
            y2 = century + y2
            if y2 < y1:
                y2 += 100
        return date(y1, 8, 1), date(y2, 5, 31)
    m = _SESSION_YEAR_RE.search(name)
    if m:
        y = int(m.group(1))
        return date(y, 8, 1), date(y + 1, 5, 31)
    today = date.today()
    return date(today.year, 8, 1), date(today.year + 1, 5, 31)


async def _find_or_create_session(db: AsyncSession, value: str) -> AcademicSession:
    v = value.strip()
    res = await db.execute(select(AcademicSession).where(func.lower(AcademicSession.name) == v.lower()))
    sess = res.scalars().first()
    if sess is not None:
        return sess
    start, end = _derive_session_dates(v)
    active_count = (await db.execute(
        select(func.count()).select_from(AcademicSession).where(AcademicSession.is_active.is_(True))
    )).scalar_one()
    sess = AcademicSession(name=v[:40], start_date=start, end_date=end, is_active=(int(active_count or 0) == 0))
    db.add(sess)
    await db.flush()
    return sess


async def _find_or_create_program(db: AsyncSession, actor: User, value: str) -> Program:
    v = value.strip()
    res = await db.execute(select(Program).where(or_(func.lower(Program.code) == v.lower(),
                                                     func.lower(Program.name) == v.lower())))
    prog = res.scalars().first()
    if prog is not None:
        return prog
    # Derive a unique internal code from the typed value (uppercased alphanumerics).
    base = re.sub(r"[^A-Z0-9]", "", v.upper())[:16] or "PROG"
    code, i = base, 1
    while True:
        clash = await db.execute(select(Program).where(Program.code == code))
        if clash.scalar_one_or_none() is None:
            break
        suffix = str(i).rjust(3, "0")
        code = f"{base[:16 - len(suffix)]}{suffix}"
        i += 1
    prog = Program(code=code, name=v[:120])
    db.add(prog)
    await db.flush()
    return prog


async def _find_or_create_class(db: AsyncSession, program_id: str, value: str) -> ClassLevel:
    v = value.strip()
    res = await db.execute(select(ClassLevel).where(ClassLevel.program_id == program_id,
                                                    func.lower(ClassLevel.name) == v.lower()))
    cls = res.scalars().first()
    if cls is not None:
        return cls
    cls = ClassLevel(program_id=program_id, name=v[:60], year=1)
    db.add(cls)
    await db.flush()
    return cls


async def _find_or_create_section(db: AsyncSession, class_level_id: str, value: str) -> Section:
    v = value.strip()
    res = await db.execute(select(Section).where(Section.class_level_id == class_level_id,
                                                 func.lower(Section.name) == v.lower()))
    sec = res.scalars().first()
    if sec is not None:
        return sec
    sec = Section(class_level_id=class_level_id, name=v[:16], capacity=40)
    db.add(sec)
    await db.flush()
    return sec


async def _resolve_placement(db: AsyncSession, actor: User,
                             program: str, class_name: str, section: str, academic_session: str):
    """Resolve four free-text names to (session, program, class, section) rows."""
    sess = await _find_or_create_session(db, academic_session)
    prog = await _find_or_create_program(db, actor, program)
    cls = await _find_or_create_class(db, prog.id, class_name)
    sec = await _find_or_create_section(db, cls.id, section)
    return sess, prog, cls, sec


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

    # Free-text placement: resolve the typed names to real rows (find-or-create),
    # then write the resolved ids back into `data` so the rest of the flow
    # (student row, enrolment, roll number) works unchanged.
    sess, prog, cls, sec = await _resolve_placement(
        db, actor, data["program"], data["class_name"], data["section"], data["academic_session"]
    )
    data["program_id"] = prog.id
    data["class_id"] = cls.id
    data["section_id"] = sec.id
    data["academic_session_id"] = sess.id

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

    # Personal fields — only set known columns (placement handled separately).
    for k in ("full_name", "phone", "date_of_birth", "gender", "account_status"):
        if data.get(k) is not None:
            setattr(student, k, data[k])

    # Free-text placement: if any of the four names is provided, resolve all of
    # them (falling back to the student's current values for any that are
    # missing) via find-or-create, then update the student's current_* ids and
    # the active enrolment in place.
    placement_keys = ("program", "class_name", "section", "academic_session")
    if any(data.get(k) for k in placement_keys):
        cur_program = await db.get(Program, student.current_program_id) if student.current_program_id else None
        cur_class = await db.get(ClassLevel, student.current_class_id) if student.current_class_id else None
        cur_section = await db.get(Section, student.current_section_id) if student.current_section_id else None
        cur_session = await db.get(AcademicSession, student.current_session_id) if student.current_session_id else None

        program_v = (data.get("program") or (cur_program.name if cur_program else "")).strip()
        session_v = (data.get("academic_session") or (cur_session.name if cur_session else "")).strip()
        class_v = (data.get("class_name") or (cur_class.name if cur_class else "")).strip()
        section_v = (data.get("section") or (cur_section.name if cur_section else "")).strip()
        if not (program_v and session_v and class_v and section_v):
            raise ValidationError("program, class_name, section and academic_session are all required to change placement.")

        sess, prog, cls, sec = await _resolve_placement(db, actor, program_v, class_v, section_v, session_v)
        student.current_program_id = prog.id
        student.current_class_id = cls.id
        student.current_section_id = sec.id
        student.current_session_id = sess.id

        # Update the active enrolment in place; recompute the roll number when
        # the section or session changed (roll numbers are unique per section+session).
        enr_res = await db.execute(select(StudentEnrolment).where(
            StudentEnrolment.student_id == student.id, StudentEnrolment.is_active.is_(True)
        ))
        enr = enr_res.scalar_one_or_none()
        moved = enr is None or enr.section_id != sec.id or enr.academic_session_id != sess.id
        if enr is None:
            enr = StudentEnrolment(
                student_id=student.id, academic_session_id=sess.id, program_id=prog.id,
                class_id=cls.id, section_id=sec.id,
                roll_number=await _next_roll_number_for_section(db, sess.id, sec.id), is_active=True,
            )
            db.add(enr)
            await db.flush()
            student.current_roll_number = enr.roll_number
        else:
            enr.program_id = prog.id
            enr.class_id = cls.id
            enr.section_id = sec.id
            enr.academic_session_id = sess.id
            if moved:
                enr.roll_number = await _next_roll_number_for_section(db, sess.id, sec.id)
                student.current_roll_number = enr.roll_number

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
