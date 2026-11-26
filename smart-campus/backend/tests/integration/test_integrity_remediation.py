"""Integration tests for the database integrity remediation (migration 0009 / D1-D18).

Each test verifies one confirmed fix at the behaviour level (via the API) or, for
constraints that are only reachable by bypassing the service, directly against
the database. These run on the SQLite test engine; PostgreSQL-specific behaviour
(partial unique indexes under real concurrency, GiST EXCLUDE) is covered by the
separate PostgreSQL test module which is not executed in this environment.
"""
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.assignments import TeacherAssignment
from app.models.examinations import GradingPolicy
from app.models.people import Student, StudentAcademicHistory, StudentEnrolment
from tests.conftest import login_as


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _teacher(admin_client, setup, email, employee_id="EMP-REM-1"):
    r = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Rem Teacher", "email": email, "employee_id": employee_id,
        "department_id": setup["department_id"], "subject": "Calculus",
        "designation": "Lecturer", "joining_date": "2022-09-01",
        "password": "Teacher!2025",
    })
    assert r.status_code == 200, r.text
    return r.json()


async def _create_student(admin_client, setup, email="rem.s1@test.edu",
                          class_id=None, section_id=None):
    r = await admin_client.post("/api/v1/students", json={
        "full_name": "Rem Student", "email": email, "phone": "+923000000001",
        "date_of_birth": "2007-03-15", "gender": "male",
        "admission_date": "2025-08-01",
        "program_id": setup["program_id"],
        "class_id": class_id or setup["class_id"],
        "section_id": section_id or setup["section_id"],
        "academic_session_id": setup["session_id"],
        "password": "Student!2025",
        "guardian": {"name": "Mr Rem", "phone": "+923001110001", "relationship_type": "Father"},
        "matric_board": "BISE Lahore", "matric_year": 2023,
        "matric_total": 1100, "matric_obtained": 950, "matric_grade": "A",
    })
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# D1 — duplicate class-wide teacher assignment rejected
# ---------------------------------------------------------------------------
async def test_d1_duplicate_classwide_assignment_rejected(admin_client, academic_setup):
    """Two class-wide (section_id NULL) assignments for the same teacher/subject/
    class/session must be rejected — the old 5-column UNIQUE treated NULL as
    distinct and silently allowed this; the new partial unique index closes it."""
    t = await _teacher(admin_client, academic_setup, "d1.t@test.edu", "EMP-D1-1")
    payload = {
        "teacher_id": t["id"], "subject_id": academic_setup["subject_id"],
        "class_id": academic_setup["class_id"], "section_id": None,
        "academic_session_id": academic_setup["session_id"],
    }
    first = await admin_client.post("/api/v1/assignments", json=payload)
    assert first.status_code == 200, first.text
    dup = await admin_client.post("/api/v1/assignments", json=payload)
    assert dup.status_code == 409, dup.text
    assert "already exists" in dup.json()["error"]["message"].lower()


async def test_d1_different_sections_same_class_allowed(admin_client, academic_setup):
    """A teacher may be assigned to two DIFFERENT sections of the same class for
    the same subject/session (independent sections) — only the duplicate of the
    SAME scope is rejected."""
    t = await _teacher(admin_client, academic_setup, "d1b.t@test.edu", "EMP-D1-2")
    sec2 = await admin_client.post("/api/v1/sections", json={
        "class_level_id": academic_setup["class_id"], "name": "B", "capacity": 40,
    })
    assert sec2.status_code == 200
    a1 = await admin_client.post("/api/v1/assignments", json={
        "teacher_id": t["id"], "subject_id": academic_setup["subject_id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
        "academic_session_id": academic_setup["session_id"],
    })
    a2 = await admin_client.post("/api/v1/assignments", json={
        "teacher_id": t["id"], "subject_id": academic_setup["subject_id"],
        "class_id": academic_setup["class_id"], "section_id": sec2.json()["id"],
        "academic_session_id": academic_setup["session_id"],
    })
    assert a1.status_code == 200 and a2.status_code == 200, (a1.text, a2.text)


# ---------------------------------------------------------------------------
# D2 — promotion writes the previous_*_id foreign keys
# ---------------------------------------------------------------------------
async def test_d2_history_previous_fk_ids_populated(admin_client, academic_setup, db):
    """Promoting a student to a new session writes a history snapshot whose
    previous_class_id/section_id/session_id reference the OLD placement (the
    values from the prior enrolment), NOT the new enrolment."""
    student = await _create_student(admin_client, academic_setup, "d2.s@test.edu")
    # Second academic session to promote into (same class/section, different session).
    sess2 = await admin_client.post("/api/v1/sessions", json={
        "name": "2026-2027", "start_date": "2026-08-01", "end_date": "2027-05-31",
        "is_active": True,
    })
    assert sess2.status_code == 200, sess2.text

    promote = await admin_client.post("/api/v1/students/promote", json={
        "student_id": student["id"], "new_program_id": academic_setup["program_id"],
        "new_class_id": academic_setup["class_id"],
        "new_section_id": academic_setup["section_id"],
        "new_academic_session_id": sess2.json()["id"], "action": "promoted",
    })
    assert promote.status_code == 200, promote.text

    # The history row's previous_*_id must equal the OLD enrolment's placement.
    old_enrol = (await db.execute(select(StudentEnrolment).where(
        StudentEnrolment.student_id == student["id"],
        StudentEnrolment.is_active.is_(False),
    ))).scalars().all()
    assert old_enrol, "expected a deactivated (history) enrolment after promotion"
    prev = old_enrol[0]
    hist = (await db.execute(select(StudentAcademicHistory).where(
        StudentAcademicHistory.student_id == student["id"]
    ))).scalar_one()
    assert str(hist.previous_class_id) == str(prev.class_id)
    assert str(hist.previous_section_id) == str(prev.section_id)
    assert str(hist.previous_session_id) == str(prev.academic_session_id)
    # And the text snapshots agree with the FK columns.
    assert str(hist.previous_class) == str(prev.class_id)


# ---------------------------------------------------------------------------
# D4 — examination program/class consistency
# ---------------------------------------------------------------------------
async def test_d4_exam_rejects_class_from_wrong_program(admin_client, academic_setup):
    """An examination whose program_id does not match the class's program is
    rejected (the redundant program_id must agree with class_levels.program_id)."""
    t = await _teacher(admin_client, academic_setup, "d4.t@test.edu", "EMP-D4-1")
    await admin_client.post("/api/v1/assignments", json={
        "teacher_id": t["id"], "subject_id": academic_setup["subject_id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
        "academic_session_id": academic_setup["session_id"],
    })
    other_prog = await admin_client.post("/api/v1/programs", json={"code": "FSC", "name": "FSc"})
    assert other_prog.status_code == 200
    resp = await admin_client.post("/api/v1/examinations", json={
        "name": "Bad Exam", "exam_type": "class_test",
        "academic_session_id": academic_setup["session_id"],
        "program_id": other_prog.json()["id"],      # wrong program for this class
        "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"],
        "subject_id": academic_setup["subject_id"],
        "max_marks": 100, "passing_marks": 40, "exam_date": "2025-09-01",
    })
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


# ---------------------------------------------------------------------------
# D4 — marks reject a student not in the exam's class
# ---------------------------------------------------------------------------
async def test_d4_marks_reject_student_not_in_exam_class(admin_client, academic_setup):
    """Marks cannot be recorded for a student who is not enrolled in the exam's
    class/section/session."""
    admin = admin_client
    # Teacher + assignment + exam for the academic_setup class.
    t = await _teacher(admin, academic_setup, "d4b.t@test.edu", "EMP-D4-2")
    await admin.post("/api/v1/assignments", json={
        "teacher_id": t["id"], "subject_id": academic_setup["subject_id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
        "academic_session_id": academic_setup["session_id"],
    })
    exam = await admin.post("/api/v1/examinations", json={
        "name": "Marks Exam", "exam_type": "class_test",
        "academic_session_id": academic_setup["session_id"],
        "program_id": academic_setup["program_id"],
        "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"],
        "subject_id": academic_setup["subject_id"],
        "max_marks": 100, "passing_marks": 40, "exam_date": "2025-09-01",
    })
    assert exam.status_code == 200, exam.text
    # A second class + section in the same program; a student placed there.
    cls2 = await admin.post("/api/v1/classes", json={
        "program_id": academic_setup["program_id"], "name": "Part 2", "year": 2,
    })
    sec2 = await admin.post("/api/v1/sections", json={
        "class_level_id": cls2.json()["id"], "name": "A", "capacity": 40,
    })
    other = await _create_student(admin, academic_setup, "d4b.s@test.edu",
                                  class_id=cls2.json()["id"], section_id=sec2.json()["id"])
    # Log in as the teacher + try to enter marks for the wrong-class student.
    await login_as(admin, "d4b.t@test.edu", "Teacher!2025")
    resp = await admin.post(f"/api/v1/examinations/{exam.json()['id']}/marks", json={
        "entries": [{"student_id": other["id"], "marks_obtained": 50, "is_absent": False}],
    })
    assert resp.status_code in (400, 403, 422), resp.text
    assert resp.status_code != 500


# ---------------------------------------------------------------------------
# D8 — at most one active enrolment per student (DB partial unique)
# ---------------------------------------------------------------------------
async def test_d8_second_active_enrolment_blocked_by_db(db, seed_departments):
    """A second is_active=True enrolment for the same student is rejected by the
    partial unique index (uq_enrolment_one_active) even when bypassing the
    service — the promote flow deactivates-before-create, so this only happens
    via direct SQL or a buggy path."""
    from app.models.academic import AcademicSession, ClassLevel, Program, Section, Subject
    from app.models.user import User
    from app.security.password import hash_password

    user = User(email="d8@x.edu", role="student", password_hash=hash_password("X"), full_name="D8")
    db.add(user); await db.flush()
    prog = Program(code="ICS", name="ICS"); db.add(prog); await db.flush()
    cls = ClassLevel(program_id=prog.id, name="Part 1", year=1); db.add(cls); await db.flush()
    sec = Section(class_level_id=cls.id, name="A", capacity=40); db.add(sec); await db.flush()
    s1 = AcademicSession(name="2025", start_date=date(2025, 8, 1), end_date=date(2026, 5, 31), is_active=True)
    s2 = AcademicSession(name="2026", start_date=date(2026, 8, 1), end_date=date(2027, 5, 31), is_active=True)
    db.add_all([s1, s2]); await db.flush()
    stu = Student(user_id=user.id, admission_number="SC-X1", full_name="D8", email="d8@x.edu",
                  admission_date=date(2025, 8, 1), current_program_id=prog.id,
                  current_class_id=cls.id, current_section_id=sec.id, current_session_id=s1.id)
    db.add(stu); await db.flush()
    db.add(StudentEnrolment(student_id=stu.id, academic_session_id=s1.id, program_id=prog.id,
                            class_id=cls.id, section_id=sec.id, roll_number=1, is_active=True))
    await db.flush()
    # A second ACTIVE enrolment in a different session must be rejected.
    db.add(StudentEnrolment(student_id=stu.id, academic_session_id=s2.id, program_id=prog.id,
                            class_id=cls.id, section_id=sec.id, roll_number=1, is_active=True))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


# ---------------------------------------------------------------------------
# D10 — at most one active grading policy (DB partial unique)
# ---------------------------------------------------------------------------
async def test_d10_second_active_grading_policy_blocked_by_db(db):
    """Activating a second grading policy without deactivating the first is
    rejected by the partial unique index (uq_grading_one_active). The service
    activate() deactivates-all-first, so this only happens via direct SQL."""
    db.add(GradingPolicy(name="P", version=1, is_active=True))
    await db.flush()
    db.add(GradingPolicy(name="P", version=2, is_active=True))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


# ---------------------------------------------------------------------------
# D14 — notice audience/target consistency
# ---------------------------------------------------------------------------
async def test_d14_program_notice_requires_program_id(admin_client, academic_setup):
    resp = await admin_client.post("/api/v1/notices", json={
        "title": "T", "content": "C", "target_audience": "program",
    })
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_d14_general_notice_rejects_stray_target(admin_client, academic_setup):
    resp = await admin_client.post("/api/v1/notices", json={
        "title": "T", "content": "C", "target_audience": "all",
        "class_id": academic_setup["class_id"],
    })
    assert resp.status_code in (400, 422), resp.text


async def test_d14_class_notice_accepted_with_class_id(admin_client, academic_setup):
    resp = await admin_client.post("/api/v1/notices", json={
        "title": "T", "content": "C", "target_audience": "class",
        "class_id": academic_setup["class_id"],
    })
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# D16 — exact overpayment prevention (Decimal, no tolerance)
# ---------------------------------------------------------------------------
async def test_d16_overpayment_exact_boundary_rejected(admin_client, academic_setup):
    """Paying up to the exact invoice amount is allowed; one unit over is
    rejected. The +0.01 float tolerance was removed (Decimal comparison)."""
    # Fee structure + invoice for 100.00
    fs = await admin_client.post("/api/v1/fees/structures", json={
        "name": "Tuition", "program_id": academic_setup["program_id"],
        "academic_session_id": academic_setup["session_id"], "amount": 100.00,
    })
    assert fs.status_code == 200, fs.text
    student = await _create_student(admin_client, academic_setup, "d16.s@test.edu")
    inv = await admin_client.post("/api/v1/fees/invoices", json={
        "student_id": student["id"], "fee_structure_id": fs.json()["id"],
        "issued_date": "2025-09-01",
    })
    assert inv.status_code == 200, inv.text
    inv_id = inv.json()["id"]
    # Pay 60 (ok), then 40 (exact — ok, total = 100), then 1 more (over).
    p1 = await admin_client.post("/api/v1/fees/payments", json={
        "invoice_id": inv_id, "amount": 60.00, "paid_at": "2025-09-02", "method": "cash",
    })
    assert p1.status_code == 200, p1.text
    p2 = await admin_client.post("/api/v1/fees/payments", json={
        "invoice_id": inv_id, "amount": 40.00, "paid_at": "2025-09-03", "method": "cash",
    })
    assert p2.status_code == 200, p2.text
    over = await admin_client.post("/api/v1/fees/payments", json={
        "invoice_id": inv_id, "amount": 1.00, "paid_at": "2025-09-04", "method": "cash",
    })
    assert over.status_code in (400, 422), over.text
    assert "exceeds" in over.json()["error"]["message"].lower()
