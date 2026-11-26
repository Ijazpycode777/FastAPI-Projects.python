"""Integration: roll-number uniqueness + enrolment integrity.

Covers the spec changes from migration 0008 / the session-wide roll model:

* Roll numbers are unique across the ENTIRE academic session — not per section.
  - duplicate roll in the same section is rejected
  - duplicate roll across different sections in the same session is rejected
  - duplicate roll across different classes/programs in the same session is rejected
  - the same roll number in a DIFFERENT session is allowed
* A student has at most one enrolment per academic session.
* student_academic_history.enrolment_id is unique (one-to-one).
* Roll-number generation considers the whole session (a second student in a
  different section of the same session gets the next session-wide roll, not
  roll 1).
* Concurrent duplicate assignments cannot bypass database uniqueness.
* Existing student history is preserved on promotion (old enrolment kept,
  deactivated; history snapshot written).
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.academic import AcademicSession, ClassLevel, Program, Section
from app.models.people import Student, StudentAcademicHistory, StudentEnrolment
from app.models.user import User
from app.security.password import hash_password
from tests.conftest import login_as


# ---------------------------------------------------------------------------
# Helpers for direct-DB constraint tests (isolated from the service layer).
# ---------------------------------------------------------------------------
async def _build_base(db):
    """Two students + one session/program/class + sections A and B."""
    sess = AcademicSession(name="2025-2026", start_date=date(2025, 8, 1),
                           end_date=date(2026, 5, 31), is_active=True)
    db.add(sess); await db.flush()
    prog = Program(code="ICS", name="ICS")
    db.add(prog); await db.flush()
    cls = ClassLevel(program_id=prog.id, name="Part 1", year=1)
    db.add(cls); await db.flush()
    sec_a = Section(class_level_id=cls.id, name="A", capacity=40)
    sec_b = Section(class_level_id=cls.id, name="B", capacity=40)
    db.add_all([sec_a, sec_b]); await db.flush()

    students = []
    for i, name in enumerate(("Alpha", "Beta"), start=1):
        u = User(email=f"rn.{name.lower()}@test.edu", role="student",
                 password_hash=hash_password("Student!2025"),
                 full_name=name, is_active=True)
        db.add(u); await db.flush()
        s = Student(user_id=u.id, admission_number=f"SC-2025-RN{i:03d}",
                    full_name=name, email=u.email, admission_date=date(2025, 8, 1),
                    account_status="active",
                    current_program_id=prog.id, current_class_id=cls.id,
                    current_section_id=sec_a.id, current_session_id=sess.id)
        db.add(s); await db.flush()
        students.append(s)
    return {"session": sess, "program": prog, "class": cls,
            "section_a": sec_a, "section_b": sec_b, "students": students}


def _enrolment(student, sess, prog, cls, sec, roll):
    return StudentEnrolment(
        student_id=student.id, academic_session_id=sess.id,
        program_id=prog.id, class_id=cls.id, section_id=sec.id,
        roll_number=roll, is_active=True,
    )


# ---------------------------------------------------------------------------
# Constraint tests (direct DB inserts — prove the DB is the final authority).
# ---------------------------------------------------------------------------
async def test_duplicate_roll_same_section_rejected(db):
    base = await _build_base(db)
    s1, s2 = base["students"]
    db.add(_enrolment(s1, base["session"], base["program"], base["class"], base["section_a"], 1))
    await db.flush()
    # Same session, same section, same roll -> IntegrityError.
    db.add(_enrolment(s2, base["session"], base["program"], base["class"], base["section_a"], 1))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


async def test_duplicate_roll_across_sections_same_session_rejected(db):
    """The key change: rolls used to be per-section, so the same roll in
    different sections of one session was allowed. It must now be rejected."""
    base = await _build_base(db)
    s1, s2 = base["students"]
    db.add(_enrolment(s1, base["session"], base["program"], base["class"], base["section_a"], 1))
    await db.flush()
    # Same session, DIFFERENT section, same roll -> IntegrityError (session-wide).
    db.add(_enrolment(s2, base["session"], base["program"], base["class"], base["section_b"], 1))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


async def test_duplicate_roll_across_classes_same_session_rejected(db):
    base = await _build_base(db)
    s1, s2 = base["students"]
    cls2 = ClassLevel(program_id=base["program"].id, name="Part 2", year=2)
    db.add(cls2); await db.flush()
    sec2 = Section(class_level_id=cls2.id, name="A", capacity=40)
    db.add(sec2); await db.flush()
    db.add(_enrolment(s1, base["session"], base["program"], base["class"], base["section_a"], 1))
    await db.flush()
    # Same session, different CLASS, same roll -> IntegrityError (session-wide).
    db.add(_enrolment(s2, base["session"], base["program"], cls2, sec2, 1))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


async def test_same_roll_different_sessions_allowed(db):
    base = await _build_base(db)
    s1, s2 = base["students"]
    sess2 = AcademicSession(name="2026-2027", start_date=date(2026, 8, 1),
                            end_date=date(2027, 5, 31), is_active=False)
    db.add(sess2); await db.flush()
    db.add(_enrolment(s1, base["session"], base["program"], base["class"], base["section_a"], 1))
    db.add(_enrolment(s2, sess2, base["program"], base["class"], base["section_b"], 1))
    await db.flush()  # both succeed — roll 1 is unique within EACH session.
    await db.commit()


async def test_student_cannot_have_two_enrolments_in_one_session(db):
    base = await _build_base(db)
    s1 = base["students"][0]
    db.add(_enrolment(s1, base["session"], base["program"], base["class"], base["section_a"], 1))
    await db.flush()
    # Same student, same session, different roll/section -> IntegrityError.
    db.add(_enrolment(s1, base["session"], base["program"], base["class"], base["section_b"], 2))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


async def test_history_enrolment_id_is_unique(db):
    base = await _build_base(db)
    s1 = base["students"][0]
    e1 = _enrolment(s1, base["session"], base["program"], base["class"], base["section_a"], 1)
    db.add(e1); await db.flush()
    db.add(StudentAcademicHistory(student_id=s1.id, enrolment_id=e1.id,
                                  action="section_change", note="first"))
    await db.flush()
    # A second history row for the SAME enrolment -> IntegrityError (one-to-one).
    db.add(StudentAcademicHistory(student_id=s1.id, enrolment_id=e1.id,
                                  action="promoted", note="second"))
    with pytest.raises(IntegrityError):
        await db.flush()
    await db.rollback()


# ---------------------------------------------------------------------------
# Behavior tests via the API (service + endpoint paths).
# ---------------------------------------------------------------------------
def _create_student_payload(setup, email, section_id):
    return {
        "full_name": email.split("@")[0], "email": email, "phone": "+923000000000",
        "date_of_birth": "2007-03-15", "gender": "male",
        "admission_date": "2025-08-01",
        "program_id": setup["program_id"], "class_id": setup["class_id"],
        "section_id": section_id, "academic_session_id": setup["session_id"],
        "password": "Student!2025",
    }


async def test_roll_generation_considers_entire_session(admin_client, academic_setup, db):
    """A second student in a DIFFERENT section of the same session must get the
    next session-wide roll (2), not roll 1 — proving generation is session-wide,
    not per-section."""
    # Create section B in the existing class.
    resp = await admin_client.post("/api/v1/sections", json={
        "class_level_id": academic_setup["class_id"], "name": "B", "capacity": 40,
    })
    assert resp.status_code == 200, resp.text
    section_b_id = resp.json()["id"]

    r1 = await admin_client.post("/api/v1/students", json=_create_student_payload(
        academic_setup, "gen.a@test.edu", academic_setup["section_id"]))
    assert r1.status_code == 200, r1.text
    r2 = await admin_client.post("/api/v1/students", json=_create_student_payload(
        academic_setup, "gen.b@test.edu", section_b_id))
    assert r2.status_code == 200, r2.text

    # The two students are in different sections of the same session. Their
    # auto-assigned rolls must be distinct and sequential across the session
    # (1 and 2), not both 1.
    rolls = sorted([
        (await db.execute(select(StudentEnrolment.roll_number).where(
            StudentEnrolment.student_id == r1.json()["id"]))).scalar_one(),
        (await db.execute(select(StudentEnrolment.roll_number).where(
            StudentEnrolment.student_id == r2.json()["id"]))).scalar_one(),
    ])
    assert rolls == [1, 2], f"session-wide generation failed: {rolls}"


async def test_roll_collision_returns_conflict_not_server_error(
    admin_client, academic_setup, monkeypatch
):
    """A roll-number collision — the outcome a concurrent create would produce
    if it raced past the advisory lock — must surface as a 409 conflict via the
    IntegrityError safety net, never a 500. The DB constraint is the final
    authority; this deterministically simulates the race by forcing the second
    create to pick an already-used roll (true inter-request concurrency cannot
    be exercised under the SQLite StaticPool test fixture, which shares one
    connection across sessions)."""
    from app.services import student_service

    # Student 1 -> enrolment with roll 1 in the session.
    r1 = await admin_client.post("/api/v1/students", json=_create_student_payload(
        academic_setup, "conflict.a@test.edu", academic_setup["section_id"]))
    assert r1.status_code == 200, r1.text

    # Force the next create to pick the SAME roll (simulating a race). The DB
    # UNIQUE(academic_session_id, roll_number) constraint must reject the insert
    # and the service must map the IntegrityError to a 409, not a 500.
    async def _fixed_roll(*_args, **_kw):
        return 1
    monkeypatch.setattr(student_service, "_next_roll_number_for_session", _fixed_roll)

    r2 = await admin_client.post("/api/v1/students", json=_create_student_payload(
        academic_setup, "conflict.b@test.edu", academic_setup["section_id"]))
    assert r2.status_code == 409, r2.text
    assert "roll" in r2.json()["error"]["message"].lower()


async def test_promote_preserves_history(admin_client, academic_setup, db):
    """Promoting a student to a new session deactivates (never deletes) the old
    enrolment and writes a history snapshot — existing history is preserved."""
    create = await admin_client.post("/api/v1/students", json=_create_student_payload(
        academic_setup, "hist.a@test.edu", academic_setup["section_id"]))
    assert create.status_code == 200, create.text
    sid = create.json()["id"]

    # Create a brand-new session and move the student into it via the edit endpoint.
    new_sess = await admin_client.post("/api/v1/sessions", json={
        "name": "2026-2027", "start_date": "2026-08-01", "end_date": "2027-05-31", "is_active": False,
    })
    assert new_sess.status_code == 200, new_sess.text
    resp = await admin_client.patch(f"/api/v1/students/{sid}", json={
        "program_id": academic_setup["program_id"], "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"], "academic_session_id": new_sess.json()["id"],
    })
    assert resp.status_code == 200, resp.text

    enrolments = (await db.execute(select(StudentEnrolment).where(
        StudentEnrolment.student_id == sid).order_by(StudentEnrolment.created_at))).scalars().all()
    assert len(enrolments) == 2  # old + new
    active = [e for e in enrolments if e.is_active]
    inactive = [e for e in enrolments if not e.is_active]
    assert len(active) == 1 and len(inactive) == 1
    # The old enrolment is kept (deactivated) — not deleted.
    assert inactive[0].academic_session_id == academic_setup["session_id"]
    # A history snapshot was written for the new (active) enrolment.
    history = (await db.execute(select(StudentAcademicHistory).where(
        StudentAcademicHistory.enrolment_id == active[0].id))).scalars().all()
    assert len(history) == 1
    assert history[0].previous_session is not None


async def test_same_session_section_change_updates_enrolment_in_place(
    admin_client, academic_setup, db
):
    """Changing a student's section WITHIN the same session updates the existing
    enrolment row in place — it does NOT create a second enrolment (which would
    violate one-enrolment-per-session) and does NOT change the roll number."""
    create = await admin_client.post("/api/v1/students", json=_create_student_payload(
        academic_setup, "sec.a@test.edu", academic_setup["section_id"]))
    assert create.status_code == 200, create.text
    sid = create.json()["id"]

    # Create section B in the same class.
    resp = await admin_client.post("/api/v1/sections", json={
        "class_level_id": academic_setup["class_id"], "name": "B", "capacity": 40,
    })
    assert resp.status_code == 200, resp.text
    sec_b_id = resp.json()["id"]

    # Move the student to section B, SAME session.
    resp = await admin_client.patch(f"/api/v1/students/{sid}", json={
        "program_id": academic_setup["program_id"], "class_id": academic_setup["class_id"],
        "section_id": sec_b_id, "academic_session_id": academic_setup["session_id"],
    })
    assert resp.status_code == 200, resp.text

    # Query fresh (no pre-loaded enrolment in the db identity map). The student
    # was the only one created in this per-test session, so its roll is 1.
    enrolments = (await db.execute(select(StudentEnrolment).where(
        StudentEnrolment.student_id == sid))).scalars().all()
    assert len(enrolments) == 1, (
        f"same-session change must update in place, got {len(enrolments)} enrolment(s)")
    assert enrolments[0].is_active is True
    assert enrolments[0].section_id == sec_b_id        # moved to section B
    assert enrolments[0].roll_number == 1              # roll preserved (session-unique)
