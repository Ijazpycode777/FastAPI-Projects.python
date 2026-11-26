"""Student management: create, update, deactivate, promote, board records."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
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
from app.utils.helpers import (
    admission_number_year_prefix,
    next_roll_number,
    pg_advisory_xact_lock,
    stable_lock_key,
)


async def _validate_placement(db: AsyncSession, program_id: str, class_id: str, section_id: str, session_id: str) -> None:
    """Validate that the four placement IDs exist and are hierarchically consistent.

    Raises NotFoundError for a missing row and ValidationError when a row exists
    but belongs to the wrong parent (class not in program, section not in class).
    Used by create_student / update_student / promote.
    """
    if await db.get(Program, program_id) is None:
        raise NotFoundError("Program not found.")
    cls = await db.get(ClassLevel, class_id)
    if cls is None:
        raise NotFoundError("Class not found.")
    if str(cls.program_id) != str(program_id):
        raise ValidationError("Class does not belong to the given program.")
    sec = await db.get(Section, section_id)
    if sec is None:
        raise NotFoundError("Section not found.")
    if str(sec.class_level_id) != str(class_id):
        raise ValidationError("Section does not belong to the given class.")
    if await db.get(AcademicSession, session_id) is None:
        raise NotFoundError("Academic session not found.")


# Placement is ID-based: the admin selects canonical program/class/section/
# session rows (managed on the Classes Distribution page) and the service
# validates them via _validate_placement. The free-text find-or-create helpers
# that used to live here were removed when the student form switched to
# dropdowns — there is no longer any "PB 21" vs "Pb 21" ambiguity because two
# students in the same class share the same class row (same ID).





async def _next_admission_number(db: AsyncSession, admitted_on: date) -> str:
    prefix = admission_number_year_prefix(admitted_on)
    count = (await db.execute(select(func.count()).select_from(Student))).scalar_one()
    return f"{prefix}-{count + 1:05d}"


async def _next_roll_number_for_session(
    db: AsyncSession, session_id: str, *, exclude_student_id: str | None = None
) -> int:
    """Smallest positive roll number not yet used anywhere in the academic session.

    Roll numbers are auto-assigned and unique across the ENTIRE session — not
    per section — so two students in different sections (or classes, or
    programs) of the same session can never share a roll number. The same roll
    may be reused in a different session. ``exclude_student_id`` keeps a
    student's own existing enrolments out of the occupied set, so re-resolving
    the same placement (or repeating a class) lets the student keep their
    current roll instead of being bumped.
    """
    # Serialize roll-number allocation for this session so two concurrent
    # creates/promotions in the same session cannot both pick the same roll.
    # The transaction-level advisory lock is held until the caller's transaction
    # commits (the enrolment row is inserted within that window). The DB unique
    # constraint (academic_session_id, roll_number) remains the final authority.
    await pg_advisory_xact_lock(db, stable_lock_key("roll_seq", session_id))
    stmt = select(StudentEnrolment.roll_number).where(
        StudentEnrolment.academic_session_id == session_id,
    )
    if exclude_student_id:
        stmt = stmt.where(StudentEnrolment.student_id != exclude_student_id)
    result = await db.execute(stmt)
    return next_roll_number([r for r in result.scalars().all()])


def _enrolment_conflict(exc: IntegrityError) -> ConflictError:
    """Map a DB uniqueness violation on student_enrolments / academic_history to
    a user-facing conflict (HTTP 409) — never a 500.

    The advisory lock prevents the common race; this is the safety net for the
    rare bypass (a cross-session collision, or a non-Postgres backend where the
    advisory lock is a no-op). The violation text carries the constraint/column
    names, which we match to a specific message."""
    text = " ".join(filter(None, [str(exc), str(getattr(exc, "orig", ""))])).lower()
    if "roll" in text:
        return ConflictError("Roll number already in use in this academic session.")
    if "enrolment" in text and "history" in text:
        return ConflictError("Enrolment already has an academic-history record.")
    if "student" in text and "session" in text:
        return ConflictError("Student already has an enrolment in this academic session.")
    return ConflictError("Enrolment conflicts with an existing record.")


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

    # ID-based placement: the admin selected canonical academic rows (managed on
    # the Classes Distribution page). Validate foreign-key consistency — no free
    # text, so two students in "PB 21" always share the same class row.
    await _validate_placement(
        db, data["program_id"], data["class_id"], data["section_id"], data["academic_session_id"]
    )

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

    roll = await _next_roll_number_for_session(db, data["academic_session_id"])
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

    try:
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
    except IntegrityError as exc:
        # Duplicate (academic_session_id, roll_number) or (student_id,
        # academic_session_id): a concurrent create in the same session raced
        # past the advisory lock (or the backend has no advisory lock). The DB
        # constraint is the final authority; surface a clean conflict, not a 500.
        await db.rollback()
        raise _enrolment_conflict(exc) from exc
    await db.refresh(student)
    return student


async def update_student(db: AsyncSession, actor: User, student: Student, data: dict[str, Any]) -> Student:
    before = await snapshot(student)

    # Personal fields — only set known columns (placement handled separately).
    for k in ("full_name", "phone", "date_of_birth", "gender", "account_status"):
        if data.get(k) is not None:
            setattr(student, k, data[k])

    # ID-based placement. The admin selects canonical rows by ID (managed on the
    # Classes Distribution page). If any placement field is supplied, ALL four
    # must be supplied together; the service validates they exist + are
    # consistent (class belongs to program, section belongs to class). On a REAL
    # change we preserve enrolment history (deactivate the previous active
    # enrolment, create a new one, write a StudentAcademicHistory snapshot) —
    # mirroring promote(). If the placement is unchanged there is nothing to
    # record, so we skip (also avoids a session/section/roll collision with the
    # existing enrolment).
    placement_keys = ("program_id", "class_id", "section_id", "academic_session_id")
    placement_supplied = [k for k in placement_keys if data.get(k) is not None]

    if placement_supplied:
        if len(placement_supplied) != 4:
            raise ValidationError(
                "program_id, class_id, section_id and academic_session_id must all be supplied together to change placement."
            )
        program_id = data["program_id"]
        class_id = data["class_id"]
        section_id = data["section_id"]
        session_id = data["academic_session_id"]
        await _validate_placement(db, program_id, class_id, section_id, session_id)

        placement_actually_changed = (
            str(program_id) != str(student.current_program_id or "")
            or str(class_id) != str(student.current_class_id or "")
            or str(section_id) != str(student.current_section_id or "")
            or str(session_id) != str(student.current_session_id or "")
        )
        if placement_actually_changed:
            prev_active = await db.execute(select(StudentEnrolment).where(
                StudentEnrolment.student_id == student.id, StudentEnrolment.is_active.is_(True)
            ))
            prev_enr = prev_active.scalar_one_or_none()

            same_session = (
                prev_enr is not None
                and str(prev_enr.academic_session_id) == str(session_id)
            )
            try:
                if same_session:
                    # Same-session placement change: a student has only ONE
                    # enrolment per session, so update the existing row in place
                    # (program/class/section) instead of creating a second row.
                    # The roll number is session-unique and stays with the student.
                    prev_enr.program_id = program_id
                    prev_enr.class_id = class_id
                    prev_enr.section_id = section_id
                    await db.flush()
                    student.current_program_id = program_id
                    student.current_class_id = class_id
                    student.current_section_id = section_id
                    student.current_session_id = session_id
                    # current_roll_number unchanged (still synced with prev_enr).
                else:
                    # Different-session change: deactivate the old enrolment (kept
                    # for history — it is in a DIFFERENT session, so no
                    # student+session conflict), create a new enrolment + history
                    # snapshot pointing at it.
                    prev_class = prev_enr.class_id if prev_enr else None
                    prev_section = prev_enr.section_id if prev_enr else None
                    prev_session = prev_enr.academic_session_id if prev_enr else None
                    prev_roll = prev_enr.roll_number if prev_enr else None
                    if prev_enr:
                        prev_enr.is_active = False
                    roll = await _next_roll_number_for_session(
                        db, session_id, exclude_student_id=student.id,
                    )
                    new_enr = StudentEnrolment(
                        student_id=student.id, academic_session_id=session_id,
                        program_id=program_id, class_id=class_id,
                        section_id=section_id, roll_number=roll, is_active=True,
                    )
                    db.add(new_enr)
                    await db.flush()
                    db.add(StudentAcademicHistory(
                        student_id=student.id, enrolment_id=new_enr.id,
                        previous_class=prev_class, previous_section=prev_section,
                        previous_session=prev_session, previous_roll_number=prev_roll,
                        # D2: relational form of the previous placement (OLD ids
                        # from prev_enr; enrolment_id is the NEW enrolment).
                        previous_class_id=prev_class,
                        previous_section_id=prev_section,
                        previous_session_id=prev_session,
                        action="section_change", note="Placement updated via student edit",
                    ))
                    student.current_program_id = program_id
                    student.current_class_id = class_id
                    student.current_section_id = section_id
                    student.current_session_id = session_id
                    student.current_roll_number = roll
            except IntegrityError as exc:
                await db.rollback()
                raise _enrolment_conflict(exc) from exc

    # Admin-set password on edit: when supplied, hash + apply it directly to the
    # linked user (the `student.user` relationship is lazy and must not be
    # navigated under async — see toggle_active). Clear the must-reset flag and
    # any login lock, and revoke the user's active sessions so a stale or stolen
    # session cannot survive a credential change. No temporary/reset flow — the
    # admin chose the credential deliberately.
    new_password = data.pop("password", None)
    if new_password:
        from app.security.password import is_strong_password
        from app.models.session import Session as SessionModel
        ok, reason = is_strong_password(new_password)
        if not ok:
            raise ValidationError(reason or "Weak password.")
        await db.execute(update(User).where(User.id == student.user_id).values(
            password_hash=hash_password(new_password),
            must_reset_password=False,
            failed_login_attempts=0,
            locked_until=None,
        ))
        await db.execute(update(SessionModel).where(
            SessionModel.user_id == student.user_id, SessionModel.revoked.is_(False),
        ).values(revoked=True))
        await record_audit(
            db, actor_id=actor.id, actor_role=actor.role,
            action="auth.password_change", resource_type="user",
            resource_id=student.user_id, after={"via": "student.update"},
        )

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

    # A promote/repeat/section_change must target a DIFFERENT placement than the
    # student's current active enrolment. An identical target is a no-op and
    # would otherwise collide with the existing (session, section, roll) row
    # when the history-preserving flow deactivates + re-creates it.
    if prev_enrolment is not None:
        same_placement = (
            str(prev_enrolment.academic_session_id) == str(data["new_academic_session_id"])
            and str(prev_enrolment.section_id) == str(data["new_section_id"])
            and str(prev_enrolment.class_id) == str(data["new_class_id"])
        )
        if same_placement:
            raise ValidationError("Student is already enrolled in this placement; nothing to promote.")

    before = await snapshot(student)

    new_session_id = data["new_academic_session_id"]
    new_class_id = data["new_class_id"]
    new_section_id = data["new_section_id"]
    new_program_id = data.get("new_program_id") or student.current_program_id

    # A student has only ONE enrolment per academic session. A placement change
    # targeting the SAME session updates the existing enrolment in place; a
    # change to a DIFFERENT session deactivates the old enrolment (kept for
    # history) and creates a new one in the new session.
    same_session = (
        prev_enrolment is not None
        and str(prev_enrolment.academic_session_id) == str(new_session_id)
    )

    try:
        if same_session:
            # Update the existing active enrolment in place. The roll number is
            # session-unique and stays with the student (no reassignment). No
            # new enrolment row + no new history row (the enrolment already has
            # its one-to-one history snapshot, if any); the change is recorded in
            # the audit log.
            prev_enrolment.program_id = new_program_id
            prev_enrolment.class_id = new_class_id
            prev_enrolment.section_id = new_section_id
            await db.flush()
            student.current_program_id = new_program_id
            student.current_class_id = new_class_id
            student.current_section_id = new_section_id
            student.current_session_id = new_session_id
            # current_roll_number unchanged (still synced with prev_enrolment).
        else:
            # Different-session promotion: deactivate the old enrolment (kept for
            # history — it is in a DIFFERENT session, so no student+session
            # conflict), create a new enrolment in the new session, and write a
            # history snapshot. The student's own enrolments are excluded from
            # roll allocation so a repeat can keep the same roll if it is free.
            prev_class = prev_enrolment.class_id if prev_enrolment else None
            prev_section = prev_enrolment.section_id if prev_enrolment else None
            prev_session = prev_enrolment.academic_session_id if prev_enrolment else None
            prev_roll = prev_enrolment.roll_number if prev_enrolment else None
            if prev_enrolment:
                prev_enrolment.is_active = False
            new_roll = await _next_roll_number_for_session(
                db, new_session_id, exclude_student_id=student.id,
            )
            new_enrolment = StudentEnrolment(
                student_id=student.id,
                academic_session_id=new_session_id,
                program_id=new_program_id,
                class_id=new_class_id,
                section_id=new_section_id,
                roll_number=new_roll,
                is_active=True,
            )
            db.add(new_enrolment)
            await db.flush()
            db.add(StudentAcademicHistory(
                student_id=student.id,
                enrolment_id=new_enrolment.id,
                previous_class=prev_class,
                previous_section=prev_section,
                previous_session=prev_session,
                previous_roll_number=prev_roll,
                # D2: relational form of the previous placement (same OLD ids as
                # the text snapshots above). enrolment_id is the NEW enrolment,
                # so these come from prev_enrolment, never from new_enrolment.
                previous_class_id=prev_class,
                previous_section_id=prev_section,
                previous_session_id=prev_session,
                action=data["action"],
                note=data.get("note"),
            ))
            student.current_program_id = new_enrolment.program_id
            student.current_class_id = new_enrolment.class_id
            student.current_section_id = new_enrolment.section_id
            student.current_session_id = new_enrolment.academic_session_id
            student.current_roll_number = new_roll
    except IntegrityError as exc:
        await db.rollback()
        raise _enrolment_conflict(exc) from exc

    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action=f"student.{data['action']}", resource_type="student", resource_id=student.id,
        before=before, after=await snapshot(student),
    )
    await db.commit()
    await db.refresh(student)
    return student
