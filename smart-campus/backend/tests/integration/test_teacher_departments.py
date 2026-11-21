"""Integration: teacher departments + manually-entered subject + classroom removal.

Covers the spec acceptance criteria:
- exactly five fixed departments (read-only, no CRUD);
- every teacher has exactly one department (FK) + one manually entered subject;
- subjects are not restricted by department;
- invalid department / missing subject → 4xx (never 500);
- one teacher can teach multiple classes (TeacherAssignment);
- classroom is gone (no /classrooms endpoint, no classroom field on entries).
"""
import pytest

from tests.conftest import login_as


FIVE_DEPARTMENTS = {"Literature", "Computer Science", "Biology",
                    "Mathematics/Statistics", "Physical Sciences"}


async def test_five_departments_listed_read_only(admin_client, academic_setup):
    resp = await admin_client.get("/api/v1/departments")
    assert resp.status_code == 200, resp.text
    names = {d["name"] for d in resp.json()}
    assert names == FIVE_DEPARTMENTS
    # No create/rename/delete endpoint — POST must be 405/404, never 201.
    post = await admin_client.post("/api/v1/departments", json={"name": "X"})
    assert post.status_code in (404, 405)


async def test_teacher_created_with_department_and_subject(admin_client, academic_setup):
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Ayesha Malik", "email": "ayesha.t@test.edu",
        "employee_id": "EMP-DEPT-1", "department_id": academic_setup["department_id"],
        "subject": "Data Structures", "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["department_id"] == academic_setup["department_id"]
    assert body["department_name"] == "Computer Science"
    assert body["subject"] == "Data Structures"


async def test_invalid_department_id_rejected_4xx(admin_client, academic_setup):
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Bad Dept", "email": "bad.dept@test.edu",
        "employee_id": "EMP-BAD-1", "department_id": "00000000-0000-0000-0000-000000000000",
        "subject": "Physics", "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert resp.status_code in (400, 404, 422), resp.text
    assert resp.status_code != 500


async def test_missing_subject_rejected_4xx(admin_client, academic_setup):
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": "No Subject", "email": "no.subj@test.edu",
        "employee_id": "EMP-NOSUBJ", "department_id": academic_setup["department_id"],
        "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_whitespace_only_subject_rejected_4xx(admin_client, academic_setup):
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Blank Subj", "email": "blank.subj@test.edu",
        "employee_id": "EMP-BLANK", "department_id": academic_setup["department_id"],
        "subject": "   ", "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


async def test_subject_not_restricted_by_department(admin_client, academic_setup):
    """Department Computer Science with subject 'Mathematics' must be accepted
    (department and subject are independent — no compatibility checks)."""
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Cross Dept", "email": "cross.t@test.edu",
        "employee_id": "EMP-CROSS-1", "department_id": academic_setup["department_id"],
        "subject": "Mathematics", "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["subject"] == "Mathematics"


async def test_teacher_update_changes_department_and_subject(admin_client, academic_setup):
    create = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Edit Me", "email": "edit.t@test.edu",
        "employee_id": "EMP-EDIT-1", "department_id": academic_setup["department_id"],
        "subject": "Algebra", "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert create.status_code == 200, create.text
    tid = create.json()["id"]
    # Pick a different department (Literature).
    depts = (await admin_client.get("/api/v1/departments")).json()
    lit_id = next(d["id"] for d in depts if d["name"] == "Literature")
    patch = await admin_client.patch(f"/api/v1/teachers/{tid}", json={
        "department_id": lit_id, "subject": "Urdu Literature",
    })
    assert patch.status_code == 200, patch.text
    assert patch.json()["department_name"] == "Literature"
    assert patch.json()["subject"] == "Urdu Literature"
    # Refresh via GET — values must persist.
    got = await admin_client.get(f"/api/v1/teachers/{tid}")
    assert got.status_code == 200
    assert got.json()["department_id"] == lit_id
    assert got.json()["subject"] == "Urdu Literature"


async def test_one_teacher_multiple_class_assignments(admin_client, academic_setup):
    """A teacher can be assigned to multiple (subject, class, section) tuples."""
    t = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Multi Class", "email": "multi.t@test.edu",
        "employee_id": "EMP-MULTI-1", "department_id": academic_setup["department_id"],
        "subject": "Calculus", "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert t.status_code == 200, t.text
    tid = t.json()["id"]
    # First assignment (the existing subject/class/section).
    a1 = await admin_client.post("/api/v1/assignments", json={
        "teacher_id": tid, "subject_id": academic_setup["subject_id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
        "academic_session_id": academic_setup["session_id"],
    })
    assert a1.status_code == 200, a1.text
    # Second class+section for the same teacher (a new section in the same class).
    sec2 = await admin_client.post("/api/v1/sections", json={
        "class_level_id": academic_setup["class_id"], "name": "B", "capacity": 40,
    })
    assert sec2.status_code == 200, sec2.text
    a2 = await admin_client.post("/api/v1/assignments", json={
        "teacher_id": tid, "subject_id": academic_setup["subject_id"],
        "class_id": academic_setup["class_id"], "section_id": sec2.json()["id"],
        "academic_session_id": academic_setup["session_id"],
    })
    assert a2.status_code == 200, a2.text
    # Both assignments exist for the one teacher.
    listed = await admin_client.get("/api/v1/assignments", params={"teacher_id": tid})
    assert listed.status_code == 200
    assert len(listed.json()) >= 2


async def test_classrooms_endpoint_gone(admin_client, academic_setup):
    """The classroom feature was removed — the list endpoint must not exist."""
    resp = await admin_client.get("/api/v1/classrooms")
    assert resp.status_code in (404, 405)


async def test_teacher_out_has_no_legacy_department_text(admin_client, academic_setup):
    """The old free-text ``department`` field must not appear on the response."""
    t = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Legacy Check", "email": "legacy.t@test.edu",
        "employee_id": "EMP-LEG-1", "department_id": academic_setup["department_id"],
        "subject": "Chemistry", "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert t.status_code == 200, t.text
    body = t.json()
    assert "department" not in body  # legacy text field removed
    assert "department_id" in body and "department_name" in body and "subject" in body
