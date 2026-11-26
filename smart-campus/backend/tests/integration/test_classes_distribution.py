"""Integration: Classes Distribution admin page — academic CRUD, referential
integrity exceptions (proper 409s, not 500s), and the aggregated distribution view.

These cover the new admin workflow: the admin first builds canonical classes /
sections / subjects / programs on the Classes Distribution page, and only rows
that are not referenced by live data can be deleted.
"""
from __future__ import annotations


async def _make_empty_class(admin_client, setup, name="Part 2", year=2):
    resp = await admin_client.post("/api/v1/classes", json={
        "program_id": setup["program_id"], "name": name, "year": year})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _make_student(admin_client, setup, email):
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": email.split("@")[0], "email": email,
        "admission_date": "2025-08-01",
        "program_id": setup["program_id"], "class_id": setup["class_id"],
        "section_id": setup["section_id"], "academic_session_id": setup["session_id"],
        "password": "Student!2025",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_class_distribution_view(admin_client, academic_setup):
    """GET /classes/distribution returns each class with program, sections,
    designated subjects and enrolment counts."""
    dist = (await admin_client.get("/api/v1/classes/distribution")).json()
    assert isinstance(dist, list) and len(dist) >= 1
    cls = next(c for c in dist if c["id"] == academic_setup["class_id"])
    assert cls["program_name"] == "ICS"
    assert cls["program_code"] == "ICS"
    assert cls["name"] == "Part 1"
    # The fixture created section A + subject CS (designated to the program).
    assert any(s["name"] == "A" for s in cls["sections"])
    assert any(s["code"] == "CS" for s in cls["subjects"])
    assert cls["enrolled"] == 0  # no students yet


async def test_delete_class_conflicts_when_students_enrolled(admin_client, academic_setup):
    """A class with an enrolled student cannot be deleted (409, not 500)."""
    await _make_student(admin_client, academic_setup, "del.s@test.edu")
    resp = await admin_client.delete(f"/api/v1/classes/{academic_setup['class_id']}")
    assert resp.status_code == 409, resp.text
    assert "enrol" in resp.json()["error"]["message"].lower()


async def test_delete_empty_class_succeeds(admin_client, academic_setup):
    """A class with no students/assignments/exams/materials/timetable can be deleted."""
    empty = await _make_empty_class(admin_client, academic_setup)
    resp = await admin_client.delete(f"/api/v1/classes/{empty['id']}")
    assert resp.status_code == 200, resp.text
    classes = (await admin_client.get("/api/v1/classes")).json()
    assert not any(c["id"] == empty["id"] for c in classes)


async def test_delete_section_conflicts_when_student_placed(admin_client, academic_setup):
    """A section with a student placed in it cannot be deleted (409)."""
    await _make_student(admin_client, academic_setup, "secdel.s@test.edu")
    resp = await admin_client.delete(f"/api/v1/sections/{academic_setup['section_id']}")
    assert resp.status_code == 409, resp.text


async def test_delete_subject_conflicts_when_assigned(admin_client, academic_setup):
    """A subject referenced by a teacher assignment cannot be deleted (409)."""
    t = await admin_client.post("/api/v1/teachers", json={
        "full_name": "T Del", "email": "t.s@test.edu", "employee_id": "EMP-D1",
        "department_id": academic_setup["department_id"], "subject": "Computer Science",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert t.status_code == 200, t.text
    a = await admin_client.post("/api/v1/assignments", json={
        "teacher_id": t.json()["id"], "subject_id": academic_setup["subject_id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
        "academic_session_id": academic_setup["session_id"],
    })
    assert a.status_code == 200, a.text

    resp = await admin_client.delete(f"/api/v1/subjects/{academic_setup['subject_id']}")
    assert resp.status_code == 409, resp.text


async def test_delete_program_conflicts_when_it_has_classes(admin_client, academic_setup):
    """A program that still has classes cannot be deleted (409)."""
    resp = await admin_client.delete(f"/api/v1/programs/{academic_setup['program_id']}")
    assert resp.status_code == 409, resp.text


async def test_rename_class_conflict_on_duplicate_name(admin_client, academic_setup):
    """Renaming a class to a name that already exists in the same program is a 409."""
    other = await _make_empty_class(admin_client, academic_setup, name="Part 2", year=2)
    resp = await admin_client.patch(f"/api/v1/classes/{other['id']}", json={"name": "Part 1"})
    assert resp.status_code == 409, resp.text


async def test_rename_class_succeeds(admin_client, academic_setup):
    """Renaming a class to a fresh name works."""
    other = await _make_empty_class(admin_client, academic_setup, name="Part 3", year=3)
    resp = await admin_client.patch(f"/api/v1/classes/{other['id']}", json={"name": "Part X"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Part X"


async def test_delete_unknown_class_returns_404(admin_client, academic_setup):
    bogus = "00000000-0000-0000-0000-000000000000"
    resp = await admin_client.delete(f"/api/v1/classes/{bogus}")
    assert resp.status_code == 404, resp.text


async def test_non_admin_cannot_access_distribution(admin_client, client, academic_setup):
    """The Classes Distribution view is admin-only — a student gets 403."""
    await _make_student(admin_client, academic_setup, "rbac.s@test.edu")
    from tests.conftest import login_as
    await login_as(client, "rbac.s@test.edu", "Student!2025")
    resp = await client.get("/api/v1/classes/distribution")
    assert resp.status_code == 403
