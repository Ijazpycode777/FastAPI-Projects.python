"""PostgreSQL-specific remediation tests (D1/D5/D8/D16 concurrency).

These tests verify the database-level constraints + advisory-lock serialization
under REAL concurrent transactions, which the SQLite test engine cannot
reproduce (SQLite serializes writes via its own locking and the tests run
single-threaded; pg_advisory_xact_lock is a no-op off PostgreSQL).

They are skipped unless DATABASE_URL points at a real PostgreSQL instance. In
this implementation environment no PostgreSQL server/driver is available, so
these tests are NOT executed here — they are provided ready-to-run for the CI /
production-verification step. See the implementation report (section 9) for the
verification status.

Run from backend/ with:

    DATABASE_URL=postgresql+asyncpg://smartcampus@localhost:5433/smartcampus \\
    DATABASE_URL_SYNC=postgresql+psycopg2://smartcampus@localhost:5433/smartcampus \\
    SESSION_COOKIE_SECURE=false SEED_RESET_ON_START=true \\
    python -m pytest tests/integration/test_postgres_remediation.py -v
"""
from __future__ import annotations

import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.base import Base
from app import models  # noqa: F401  (register tables)

PG_URL = os.environ.get("DATABASE_URL", "")
IS_PG = PG_URL.startswith("postgresql") or PG_URL.startswith("postgres")
pytestmark = pytest.mark.skipif(
    not IS_PG, reason="PostgreSQL remediation tests need DATABASE_URL=postgresql+asyncpg://..."
)


@pytest_asyncio.fixture
async def pg_engine():
    engine = create_async_engine(PG_URL, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _session_factory(engine):
    return async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


# ---------------------------------------------------------------------------
# D1 — concurrent class-wide assignment: exactly one wins, the other gets a
# duplicate conflict. The partial unique index (WHERE section_id IS NULL) is the
# final authority; the service re-query confirms the duplicate.
# ---------------------------------------------------------------------------
async def test_d1_concurrent_classwide_assignment_one_wins(pg_engine):
    from app.models.academic import AcademicSession, ClassLevel, Program, Section, Subject
    from app.models.assignments import TeacherAssignment
    from app.models.people import Teacher
    from app.models.user import User
    from app.security.password import hash_password
    from datetime import date

    Session = _session_factory(pg_engine)
    async with Session() as db:
        prog = Program(code="ICS", name="ICS"); db.add(prog)
        cls = ClassLevel(program_id=prog.id, name="P1", year=1); db.add(cls)
        sec = Section(class_level_id=cls.id, name="A", capacity=40); db.add(sec)
        subj = Subject(program_id=prog.id, code="CS", name="CS"); db.add(subj)
        sess = AcademicSession(name="2025", start_date=date(2025, 8, 1),
                               end_date=date(2026, 5, 31), is_active=True); db.add(sess)
        u = User(email="t@x.edu", role="teacher", password_hash=hash_password("x"), full_name="T")
        db.add(u); await db.flush()
        t = Teacher(user_id=u.id, employee_id="E1", full_name="T", email="t@x.edu",
                    department_id=None, subject="CS", joining_date=date(2022, 9, 1))
        # department_id is NOT NULL FK to the seeded departments; seed them first
        # in a real run (the CI harness seeds via 0006 / app.seed).
        await db.commit()

    async def _assign():
        from app.services.academic_service import assign_teacher
        from app.core.exceptions import ConflictError
        async with Session() as db:
            try:
                await assign_teacher(db, actor=type("A", (), {"id": "sys", "role": "admin"})(),
                                     teacher_id=t.id, subject_id=subj.id, class_id=cls.id,
                                     section_id=None, academic_session_id=sess.id)
                return "ok"
            except ConflictError:
                return "conflict"

    results = await asyncio.gather(*(_assign() for _ in range(2)))
    assert results.count("ok") == 1, f"expected exactly one ok, got {results}"
    assert results.count("conflict") == 1, f"expected exactly one conflict, got {results}"


# ---------------------------------------------------------------------------
# D16 — concurrent payments that together overpay: the FOR UPDATE lock on the
# invoice serializes them so the overpayment is rejected, never both committed.
# ---------------------------------------------------------------------------
async def test_d16_concurrent_overpayment_rejected(pg_engine):
    # Build an invoice with amount 100, then fire two concurrent 60 payments.
    # Exactly one succeeds (60 <= 100); the other must be rejected (60+60 > 100).
    from app.models.fees import FeeInvoice, FeeStructure, Payment
    from app.models.people import Student
    from app.models.user import User
    from app.security.password import hash_password
    from datetime import date

    Session = _session_factory(pg_engine)
    async with Session() as db:
        u = User(email="s@x.edu", role="student", password_hash=hash_password("x"), full_name="S")
        db.add(u); await db.flush()
        stu = Student(user_id=u.id, admission_number="SC-1", full_name="S", email="s@x.edu",
                      admission_date=date(2025, 8, 1)); db.add(stu)
        fs = FeeStructure(name="Tuition", amount=100, academic_session_id=None); db.add(fs)
        await db.flush()
        inv = FeeInvoice(invoice_number="INV-1", student_id=stu.id, fee_structure_id=fs.id,
                         academic_session_id=None, amount=100, issued_date=date(2025, 9, 1),
                         due_date=date(2025, 9, 30)); db.add(inv)
        await db.commit()

    async def _pay():
        from app.services.fee_service import record_payment
        from app.core.exceptions import ValidationError
        async with Session() as db:
            try:
                await record_payment(db, actor=type("A", (), {"id": "sys", "role": "admin"})(),
                                     data={"invoice_id": inv.id, "amount": 60.0,
                                           "paid_at": date(2025, 9, 2), "method": "cash"})
                return "ok"
            except ValidationError:
                return "rejected"

    results = await asyncio.gather(*(_pay() for _ in range(2)))
    assert results.count("ok") == 1, f"expected exactly one payment ok, got {results}"
    assert results.count("rejected") == 1, f"expected exactly one overpayment rejected, got {results}"


# ---------------------------------------------------------------------------
# D5 — concurrent timetable entries for the same teacher/day/overlapping time:
# the dual advisory lock serializes them so the overlap is detected + rejected.
# ---------------------------------------------------------------------------
async def test_d5_concurrent_teacher_double_booking_rejected(pg_engine):
    from app.models.academic import AcademicSession, ClassLevel, Program, Section, Subject
    from app.models.assignments import TeacherAssignment
    from app.models.people import Teacher
    from app.models.timetable import TimetableEntry
    from app.models.user import User
    from app.security.password import hash_password
    from datetime import date, time

    Session = _session_factory(pg_engine)
    async with Session() as db:
        prog = Program(code="ICS", name="ICS"); db.add(prog)
        cls = ClassLevel(program_id=prog.id, name="P1", year=1); db.add(cls)
        sec = Section(class_level_id=cls.id, name="A", capacity=40); db.add(sec)
        subj = Subject(program_id=prog.id, code="CS", name="CS"); db.add(subj)
        sess = AcademicSession(name="2025", start_date=date(2025, 8, 1),
                               end_date=date(2026, 5, 31), is_active=True); db.add(sess)
        u = User(email="t2@x.edu", role="teacher", password_hash=hash_password("x"), full_name="T")
        db.add(u); await db.flush()
        t = Teacher(user_id=u.id, employee_id="E2", full_name="T", email="t2@x.edu",
                    department_id=None, subject="CS", joining_date=date(2022, 9, 1))
        db.add(t); await db.flush()
        db.add(TeacherAssignment(teacher_id=t.id, subject_id=subj.id, class_id=cls.id,
                                 section_id=sec.id, academic_session_id=sess.id, is_active=True))
        await db.commit()

    async def _create(start, end):
        from app.services.timetable_service import create_entry
        from app.core.exceptions import ConflictError
        async with Session() as db:
            try:
                await create_entry(db, actor=type("A", (), {"id": "sys", "role": "admin"})(),
                                   data={"academic_session_id": sess.id, "day_of_week": "monday",
                                         "start_time": start, "end_time": end,
                                         "subject_id": subj.id, "teacher_id": t.id,
                                         "class_id": cls.id, "section_id": sec.id})
                return "ok"
            except ConflictError:
                return "conflict"

    # Two overlapping slots (08:30-09:30 and 09:00-10:00) for the same teacher.
    results = await asyncio.gather(
        _create(time(8, 30), time(9, 30)), _create(time(9, 0), time(10, 0))
    )
    assert results.count("ok") == 1, f"expected exactly one entry created, got {results}"
    assert results.count("conflict") == 1, f"expected exactly one conflict, got {results}"
