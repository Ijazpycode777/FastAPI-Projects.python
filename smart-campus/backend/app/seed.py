"""Demo data seeding. Creates a coherent dataset demonstrating every module.

Demo accounts (synthetic data only — never real student information):
  admin@smartcampus.edu   / ChangeMe!2025
  teacher.sarah@smartcampus.edu / Teacher!2025
  student.ali@smartcampus.edu   / Student!2025
  student.fatima@smartcampus.edu / Student!2025

Idempotent: safe to re-run; existing demo rows are left in place.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import date, time, timedelta

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database.session import AsyncSessionLocal, engine
from app.models.academic import AcademicSession, ClassLevel, Classroom, Program, Section, Subject
from app.models.assignments import TeacherAssignment
from app.models.attendance import AttendanceRecord, TeacherAttendance
from app.models.campus import CampusShift
from app.models.examinations import Examination, GradingBoundary, GradingPolicy, StudentMark
from app.models.fees import FeeInvoice, FeeStructure, Payment
from app.models.materials import StudyMaterial
from app.models.people import BoardExaminationRecord, Guardian, Student, StudentEnrolment, Teacher
from app.models.timetable import TimetableEntry
from app.models.user import User
from app.security.password import hash_password
from app.services.academic_service import assign_teacher
from app.services.exam_service import enter_marks, finalize as finalize_exam, publish as publish_exam
from app.services.grading_service import activate as activate_policy, create_policy

log = logging.getLogger("smartcampus.seed")

DEMO_PASSWORDS = {
    "admin": "ChangeMe!2025",
    "teacher": "Teacher!2025",
    "student": "Student!2025",
}

# Fixed 32-bit key for the cluster-wide advisory lock guarding seeding/admin
# bootstrap. Advisory locks are global across all connections/replicas, so only
# one worker (or container) ever seeds at a time, even with --workers N > 1.
_SEED_ADVISORY_KEY = 0x5C4A7C01


def _is_postgres() -> bool:
    url = settings.database_url or ""
    return url.startswith("postgresql") or url.startswith("postgres")


@asynccontextmanager
async def _seed_lock(*, blocking: bool = False):
    """Hold a cluster-wide advisory lock for the duration of seeding.

    Why this design (fix for the lock-lifecycle bug):

    * The lock is taken on a **dedicated connection** checked out directly from
      the engine (``engine.connect()``), NOT on the seeding ``AsyncSession``.
      An ``AsyncSession`` returns its connection to the pool on every
      ``commit()``, so a *session-level* advisory lock acquired through it can
      orphan onto a pooled connection and be unlocked on the wrong connection
      (or never released). Holding a dedicated connection for the whole
      operation guarantees acquire and release use the same physical connection.
    * We use the **transaction-level** variant ``pg_try_advisory_xact_lock``
      (or the blocking ``pg_advisory_xact_lock``). Transaction-level advisory
      locks are released automatically when the transaction ends — commit OR
      rollback — so the lock is freed the instant the dedicated connection's
      transaction ends, including on exceptions and asyncio cancellation. It
      can never remain stuck in the connection pool.
    * The dedicated connection/transaction is held open across the ``yield`` so
      the lock stays held for the full seeding; the actual seeding DML runs on
      the ``AsyncSession``'s own connections, independent of the lock
      connection. Normal commits inside seeding therefore cannot release or
      invalidate the lock.
    * On non-Postgres backends (unit tests) this is a no-op yielding True.

    Yields ``True`` if the lock was acquired. For ``blocking=True`` the call
    waits until the lock is acquired and always yields ``True``.
    """
    if not _is_postgres():
        yield True
        return
    fn = "pg_advisory_xact_lock" if blocking else "pg_try_advisory_xact_lock"
    async with engine.connect() as conn:
        # Explicit transaction held open across the yield so the xact lock stays
        # held for the full duration of the caller's work.
        async with conn.begin():
            acquired = bool((await conn.execute(
                text(f"SELECT {fn}(:k)"), {"k": _SEED_ADVISORY_KEY}
            )).scalar_one())
            yield acquired
        # conn.begin() ends here -> commit on normal exit, rollback on
        # exception -> xact advisory lock auto-released. The dedicated
        # connection returns to the pool clean.


async def _get_or_create(db, model, filter_clause, **kwargs):
    """Fetch an existing row or insert a new one.

    The object is created and added **inside** the SAVEPOINT (not before it) so
    that no autoflush can emit the INSERT outside the savepoint. On a uniqueness
    conflict the SAVEPOINT rolls back only that insert, leaving the outer
    seeding transaction usable, and we re-fetch the winning row. Under normal
    operation the advisory lock makes this conflict path unreachable.
    """
    obj = (await db.execute(select(model).where(*filter_clause))).scalar_one_or_none()
    if obj is not None:
        return obj
    try:
        async with db.begin_nested():
            obj = model(**kwargs)
            db.add(obj)
            await db.flush()
    except IntegrityError:
        # Concurrent insert won the race; SAVEPOINT rolled back, outer
        # transaction is intact. Return the row that now exists.
        return (await db.execute(select(model).where(*filter_clause))).scalar_one()
    return obj


def _minimal_pdf() -> bytes:
    """A small but valid PDF (one page) for the demo study material, so the
    download endpoint never advertises a file that does not exist."""
    from io import BytesIO

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle("Intro to Algorithms - Lecture Notes")
    c.drawString(72, 720, "Intro to Algorithms - Lecture Notes (demo)")
    c.drawString(72, 700, "Week 1-4 notes. Synthetic demo content.")
    c.showPage()
    c.save()
    return buf.getvalue()


def _check_admin_password_policy(password: str) -> None:
    """Validate the seeded admin password; warn (never crash) when weak.

    The env-var admin is a permanent, always-accessible account, so a weak or
    default password never prevents startup — it only emits a loud warning so an
    operator notices and rotates it. In non-production the built-in default is
    permitted silently.
    """
    if not settings.is_production:
        return
    from app.security.password import is_strong_password

    if password == "ChangeMe!2025":
        log.warning(
            "SEED_ADMIN_PASSWORD is the built-in default; set a strong, unique "
            "administrator password."
        )
        return
    ok, reason = is_strong_password(password)
    if not ok:
        log.warning(
            "SEED_ADMIN_PASSWORD is weak (%s); set a strong, unique password.",
            reason,
        )


async def bootstrap_admin() -> bool:
    """Ensure the permanent seeded administrator exists and is always usable.

    Driven by ``SEED_ADMIN_EMAIL`` / ``SEED_ADMIN_PASSWORD``. On EVERY startup:

      * Creates the admin if it does not exist; OR
      * Re-syncs the existing admin's password to ``SEED_ADMIN_PASSWORD`` so the
        configured credential ALWAYS works — restarts are NOT non-destructive for
        this account. This also clears any lockout and ``must_reset_password``
        flag, so the account is usable immediately even after failed attempts.
      * Forces ``role='admin'``, ``is_active=True``, ``must_reset_password=False``.
      * Never seeds demo students/teachers (dev-only, via ``seed_demo_data``).
      * If the configured email already belongs to a teacher or student, it does
        NOT report success and does NOT modify that account — the deployment
        fails loudly so an operator can set SEED_ADMIN_EMAIL to an unused address.
      * Weak/default admin passwords produce a WARNING (not a crash) so the app
        always starts and the admin is always reachable.
      * Idempotent and serialized across workers/replicas by a **blocking**
        transaction-level advisory lock.
      * The password is never logged.

    Returns ``True`` only if a usable administrator (role == 'admin' AND active)
    exists for the configured email after the call.
    """
    email = settings.seed_admin_email.strip().lower()
    if not settings.seed_admin_password:
        raise RuntimeError(
            "SEED_ADMIN_PASSWORD is not set; cannot bootstrap administrator."
        )
    _check_admin_password_policy(settings.seed_admin_password)
    pw_hash = hash_password(settings.seed_admin_password)
    async with _seed_lock(blocking=True):
        async with AsyncSessionLocal() as db:
            existing = (await db.execute(
                select(User).where(User.email == email)
            )).scalar_one_or_none()
            if existing is None:
                db.add(User(
                    email=email,
                    role="admin",
                    password_hash=pw_hash,
                    full_name="System Administrator",
                    is_active=True,
                    must_reset_password=False,
                ))
                await db.commit()
                log.info("Bootstrap: created administrator account for %s.", email)
            elif existing.role != "admin":
                # The configured email is taken by a non-admin account (teacher or
                # student). Do NOT silently promote it or reset its password —
                # report not-usable so startup fails for an operator to resolve.
                log.error(
                    "Bootstrap: %s already exists with role %r (not 'admin'). "
                    "Refusing to reuse or modify it; set SEED_ADMIN_EMAIL to an "
                    "unused address.", email, existing.role,
                )
            else:
                # Permanent admin: re-sync the password and account flags to the
                # configured env values on every startup so SEED_ADMIN_PASSWORD
                # ALWAYS works (even if it was changed in-app or the account got
                # locked by repeated failed attempts). must_reset_password is
                # forced off so the account is usable immediately on first login.
                existing.password_hash = pw_hash
                existing.role = "admin"
                existing.is_active = True
                existing.must_reset_password = False
                existing.locked_until = None
                existing.failed_login_attempts = 0
                await db.commit()
                log.info(
                    "Bootstrap: administrator %s re-synced to SEED_ADMIN_PASSWORD "
                    "(password, flags and lockout reset).", email,
                )
    # Verify a usable ADMIN (role == 'admin' AND active) exists for the email.
    async with AsyncSessionLocal() as db:
        admin = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    return admin is not None and admin.role == "admin" and admin.is_active


async def seed_demo_data() -> None:
    async with _seed_lock() as acquired:
        if not acquired:
            log.info("Demo seeding already in progress on another worker; skipping.")
            return
        async with AsyncSessionLocal() as db:
            # Admin
            admin = await _get_or_create(
                db, User, [User.email == settings.seed_admin_email.strip().lower()],
                email=settings.seed_admin_email.strip().lower(), role="admin",
                password_hash=hash_password(settings.seed_admin_password),
                full_name="System Administrator", is_active=True,
            )

            # Academic session
            session = await _get_or_create(
                db, AcademicSession, [AcademicSession.name == "2025-2026"],
                name="2025-2026", start_date=date(2025, 8, 1), end_date=date(2026, 5, 31), is_active=True,
            )

            # Programs
            ics = await _get_or_create(db, Program, [Program.code == "ICS"],
                                       code="ICS", name="Intermediate in Computer Science")
            fsc = await _get_or_create(db, Program, [Program.code == "FSc"],
                                       code="FSc", name="Faculty of Science (Pre-Engineering)")
            icom = await _get_or_create(db, Program, [Program.code == "I.Com"],
                                        code="I.Com", name="Intermediate in Commerce")

            # Classes (parts)
            ics_p1 = await _get_or_create(db, ClassLevel, [ClassLevel.program_id == ics.id, ClassLevel.name == "Part 1"],
                                          program_id=ics.id, name="Part 1", year=1)
            ics_p2 = await _get_or_create(db, ClassLevel, [ClassLevel.program_id == ics.id, ClassLevel.name == "Part 2"],
                                          program_id=ics.id, name="Part 2", year=2)

            # Sections
            ics_p1_a = await _get_or_create(db, Section, [Section.class_level_id == ics_p1.id, Section.name == "A"],
                                            class_level_id=ics_p1.id, name="A", capacity=40)
            ics_p1_b = await _get_or_create(db, Section, [Section.class_level_id == ics_p1.id, Section.name == "B"],
                                            class_level_id=ics_p1.id, name="B", capacity=40)

            # Subjects
            prog_math = await _get_or_create(db, Subject, [Subject.program_id == ics.id, Subject.code == "MATH"],
                                             program_id=ics.id, code="MATH", name="Mathematics")
            prog_cs = await _get_or_create(db, Subject, [Subject.program_id == ics.id, Subject.code == "CS"],
                                           program_id=ics.id, code="CS", name="Computer Science")
            prog_phy = await _get_or_create(db, Subject, [Subject.program_id == ics.id, Subject.code == "PHY"],
                                            program_id=ics.id, code="PHY", name="Physics")

            # Classrooms
            r101 = await _get_or_create(db, Classroom, [Classroom.room_number == "101"],
                                        room_number="101", building="Main", capacity=40)
            r102 = await _get_or_create(db, Classroom, [Classroom.room_number == "102"],
                                        room_number="102", building="Main", capacity=40)

            # Campus shifts (Morning / Evening)
            morning = await _get_or_create(
                db, CampusShift, [CampusShift.code == "MORNING"],
                name="Morning", code="MORNING", start_time=time(8, 0), end_time=time(14, 0), is_active=True,
            )
            evening = await _get_or_create(
                db, CampusShift, [CampusShift.code == "EVENING"],
                name="Evening", code="EVENING", start_time=time(14, 0), end_time=time(20, 0), is_active=True,
            )

            # Teacher
            teacher_user = await _get_or_create(
                db, User, [User.email == "teacher.sarah@smartcampus.edu"],
                email="teacher.sarah@smartcampus.edu", role="teacher",
                password_hash=hash_password(DEMO_PASSWORDS["teacher"]),
                full_name="Sarah Khan", is_active=True,
            )
            teacher = await _get_or_create(
                db, Teacher, [Teacher.email == "teacher.sarah@smartcampus.edu"],
                user_id=teacher_user.id, employee_id="EMP-001",
                full_name="Sarah Khan", email="teacher.sarah@smartcampus.edu",
                phone="+923000000001", department="Computer Science",
                designation="Senior Lecturer", joining_date=date(2022, 9, 1),
                campus_shift_id=morning.id, employment_status="active",
            )

            # Assign teacher to ICS Part 1 A for CS and MATH
            for subj, sec in [(prog_cs, ics_p1_a), (prog_math, ics_p1_a)]:
                await _get_or_create(
                    db, TeacherAssignment,
                    [TeacherAssignment.teacher_id == teacher.id,
                     TeacherAssignment.subject_id == subj.id,
                     TeacherAssignment.class_id == ics_p1.id,
                     TeacherAssignment.section_id == sec.id,
                     TeacherAssignment.academic_session_id == session.id],
                    teacher_id=teacher.id, subject_id=subj.id, class_id=ics_p1.id,
                    section_id=sec.id, academic_session_id=session.id, is_active=True,
                )

            # Students
            students_data = [
                ("student.ali@smartcampus.edu", "Ali Ahmed", "male", "Father", "+923001110001"),
                ("student.fatima@smartcampus.edu", "Fatima Noor", "female", "Mother", "+923001110002"),
                ("student.bilal@smartcampus.edu", "Bilal Raza", "male", "Father", "+923001110003"),
            ]
            created_students = []
            for i, (email, name, gender, gtype, gphone) in enumerate(students_data, start=1):
                su = await _get_or_create(
                    db, User, [User.email == email],
                    email=email, role="student",
                    password_hash=hash_password(DEMO_PASSWORDS["student"]),
                    full_name=name, is_active=True,
                )
                guardian = await _get_or_create(
                    db, Guardian, [Guardian.phone == gphone, Guardian.name == f"{name.split()[0]}'s {gtype}"],
                    name=f"{name.split()[0]}'s {gtype}", phone=gphone, relationship_type=gtype,
                )
                student = await _get_or_create(
                    db, Student, [Student.email == email],
                    user_id=su.id, admission_number=f"SC-2025-{i:05d}",
                    full_name=name, email=email, phone=gphone,
                    date_of_birth=date(2007, 1 + i, 10), gender=gender,
                    guardian_id=guardian.id, admission_date=date(2025, 8, 1),
                    account_status="active",
                    current_program_id=ics.id, current_class_id=ics_p1.id,
                    current_section_id=ics_p1_a.id, current_session_id=session.id,
                    current_roll_number=i, campus_shift_id=morning.id,
                )
                await _get_or_create(
                    db, StudentEnrolment,
                    [StudentEnrolment.student_id == student.id, StudentEnrolment.academic_session_id == session.id],
                    student_id=student.id, academic_session_id=session.id,
                    program_id=ics.id, class_id=ics_p1.id, section_id=ics_p1_a.id,
                    roll_number=i, campus_shift_id=morning.id, is_active=True,
                )
                # Board records
                await _get_or_create(
                    db, BoardExaminationRecord,
                    [BoardExaminationRecord.student_id == student.id, BoardExaminationRecord.level == "matric"],
                    student_id=student.id, level="matric", board="BISE Lahore",
                    examination_year=2023, total_marks=1100, obtained_marks=850 + i, grade="A",
                )
                created_students.append(student)

            # Timetable entries
            tt_entries = []
            for day in ("monday", "tuesday", "wednesday"):
                for subj, room, start, end in [(prog_cs, r101, time(8, 30), time(9, 30)),
                                               (prog_math, r102, time(9, 30), time(10, 30))]:
                    entry = await _get_or_create(
                        db, TimetableEntry,
                        [TimetableEntry.teacher_id == teacher.id,
                         TimetableEntry.day_of_week == day,
                         TimetableEntry.start_time == start,
                         TimetableEntry.subject_id == subj.id,
                         TimetableEntry.class_id == ics_p1.id],
                        academic_session_id=session.id, campus_shift_id=morning.id, day_of_week=day,
                        start_time=start, end_time=end, subject_id=subj.id,
                        teacher_id=teacher.id, class_id=ics_p1.id, section_id=ics_p1_a.id,
                        classroom_id=room.id, is_cancelled=False,
                    )
                    tt_entries.append(entry)

            # Attendance for the first student over the timetable entries
            if tt_entries and created_students:
                statuses = ["present", "late", "present", "absent", "excused", "present"]
                from datetime import datetime, timezone
                today = date.today()
                for i, e in enumerate(tt_entries[:6]):
                    for j, st in enumerate(created_students):
                        exists = await db.execute(select(AttendanceRecord).where(
                            AttendanceRecord.student_id == st.id,
                            AttendanceRecord.timetable_entry_id == e.id,
                            AttendanceRecord.attendance_date == today - timedelta(days=i),
                        ))
                        if exists.scalar_one_or_none() is None:
                            db.add(AttendanceRecord(
                                student_id=st.id, timetable_entry_id=e.id,
                                subject_id=str(e.subject_id), teacher_id=teacher.id,
                                class_id=ics_p1.id, section_id=ics_p1_a.id,
                                academic_session_id=session.id,
                                attendance_date=today - timedelta(days=i),
                                status=statuses[i % len(statuses)] if j == 0 else "present",
                                marked_by=admin.id, marked_at=datetime.now(timezone.utc),
                            ))

            # Teacher self-attendance today
            from datetime import datetime, timezone
            ta = await _get_or_create(
                db, TeacherAttendance,
                [TeacherAttendance.teacher_id == teacher.id, TeacherAttendance.attendance_date == date.today()],
                teacher_id=teacher.id, attendance_date=date.today(),
                check_in_at=datetime.now(timezone.utc).replace(hour=8, minute=35, second=0, microsecond=0),
                check_out_at=None, status="present", work_minutes=0,
            )

            # Grading policy
            policy = await _get_or_create(
                db, GradingPolicy, [GradingPolicy.name == "Default", GradingPolicy.version == 1],
                name="Default", version=1, is_active=True, description="Standard 5-band policy",
            )
            bounds = [
                ("F", 0, 40, False), ("C", 40, 50, True), ("B", 50, 70, True),
                ("A", 70, 85, True), ("A+", 85, 100, True),
            ]
            for name, lo, hi, p in bounds:
                await _get_or_create(
                    db, GradingBoundary,
                    [GradingBoundary.policy_id == policy.id, GradingBoundary.grade_name == name],
                    policy_id=policy.id, grade_name=name, min_percentage=lo, max_percentage=hi,
                    is_pass=p,
                )

            # Examination + marks
            exam = await _get_or_create(
                db, Examination,
                [Examination.name == "CS Midterm 2025", Examination.subject_id == prog_cs.id,
                 Examination.class_id == ics_p1.id],
                name="CS Midterm 2025", exam_type="midterm",
                academic_session_id=session.id, program_id=ics.id, class_id=ics_p1.id,
                section_id=ics_p1_a.id, subject_id=prog_cs.id, max_marks=100, passing_marks=40,
                exam_date=date(2025, 10, 15), status="draft", created_by=admin.id,
                grading_policy_id=policy.id,
            )
            # Enter marks if none yet
            existing_marks = await db.execute(select(StudentMark).where(StudentMark.examination_id == exam.id))
            if existing_marks.scalars().first() is None:
                await enter_marks(db, admin, teacher.id, {
                    "examination_id": str(exam.id),
                    "entries": [
                        {"student_id": str(created_students[0].id), "marks_obtained": 82, "is_absent": False},
                        {"student_id": str(created_students[1].id), "marks_obtained": 91, "is_absent": False},
                        {"student_id": str(created_students[2].id), "marks_obtained": 0, "is_absent": True},
                    ],
                })
                await publish_exam(db, admin, exam)
                await finalize_exam(db, admin, exam)

            # Fee structure + invoice + payment for first student
            fee_struct = await _get_or_create(
                db, FeeStructure, [FeeStructure.name == "ICS Tuition 2025-2026"],
                name="ICS Tuition 2025-2026", program_id=ics.id, class_id=ics_p1.id,
                academic_session_id=session.id, amount=50000, frequency="annual",
                due_after_days=30, is_active=True,
            )
            inv = await _get_or_create(
                db, FeeInvoice, [FeeInvoice.student_id == created_students[0].id, FeeInvoice.fee_structure_id == fee_struct.id],
                invoice_number=f"INV-2025-00001", student_id=created_students[0].id,
                fee_structure_id=fee_struct.id, academic_session_id=session.id,
                amount=50000, issued_date=date(2025, 8, 1), due_date=date(2025, 8, 31),
                status="partial", issued_by=admin.id,
            )
            pay = await _get_or_create(
                db, Payment, [Payment.invoice_id == inv.id, Payment.amount == 20000],
                invoice_id=inv.id, student_id=created_students[0].id, amount=20000,
                paid_at=date(2025, 8, 5), method="bank_transfer", reference="BNK-001",
                recorded_by=admin.id, receipt_number="RCP-000001",
            )
            # Two more payments in later months so the admin fee-collection trend
            # chart has a real multi-month series (not a single point).
            await _get_or_create(
                db, Payment, [Payment.receipt_number == "RCP-000002"],
                invoice_id=inv.id, student_id=created_students[0].id, amount=10000,
                paid_at=date(2025, 10, 10), method="card", reference="CARD-002",
                recorded_by=admin.id, receipt_number="RCP-000002",
            )
            await _get_or_create(
                db, Payment, [Payment.receipt_number == "RCP-000003"],
                invoice_id=inv.id, student_id=created_students[0].id, amount=8000,
                paid_at=date(2025, 12, 12), method="cash", reference="CSH-003",
                recorded_by=admin.id, receipt_number="RCP-000003",
            )

            # Student leave for the first student covering the first Mon-Wed of
            # the session (Aug 4-6 2025). The timetable has lectures on Mon/Tue/Wed,
            # so this yields real "leave" sessions in the attendance donut.
            from app.models.attendance import LeaveRecord as _LeaveRecord
            await _get_or_create(
                db, _LeaveRecord,
                [_LeaveRecord.student_id == created_students[0].id,
                 _LeaveRecord.start_date == date(2025, 8, 4)],
                person_type="student", student_id=created_students[0].id, teacher_id=None,
                start_date=date(2025, 8, 4), end_date=date(2025, 8, 6),
                reason="Medical leave (fever)", status="approved", approved_by=admin.id,
            )

            # Study material — write a real synthetic PDF so the download
            # endpoint never advertises a file that does not exist.
            import io
            from app.services.storage import get_storage
            material_key = "materials/seed-algorithms.pdf"
            pdf_bytes = _minimal_pdf()
            get_storage().save(material_key, io.BytesIO(pdf_bytes), "application/pdf")
            await _get_or_create(
                db, StudyMaterial, [StudyMaterial.title == "Intro to Algorithms — Lecture Notes"],
                title="Intro to Algorithms — Lecture Notes", description="Week 1-4 notes",
                subject_id=prog_cs.id, class_id=ics_p1.id, section_id=ics_p1_a.id,
                uploaded_by=teacher_user.id, storage_backend="local",
                storage_key=material_key, file_name="algorithms.pdf",
                file_size=len(pdf_bytes), content_type="application/pdf", is_active=True,
            )

            await db.commit()
            log.info("Seeded demo data: 1 admin, 1 teacher, 3 students, exams, fees, materials.")
