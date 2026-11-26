"""Integration: admin password management + admin creation.

Covers the post-remediation requirements:
- only an admin can change a student's/teacher's password, set directly on edit
  (no temporary/reset flow) — the chosen credential works immediately;
- editing without supplying a password leaves the current password untouched;
- a weak password on edit is rejected with a clean 4xx (never a 500);
- an admin can create another admin account (assign more admins);
- non-admins cannot create admins (403);
- duplicate-email admin creation is rejected (409);
- admins are listable.
"""
import pytest

from tests.conftest import login_as


async def _make_teacher(admin_client, academic_setup, email, employee_id):
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": "T " + employee_id, "email": email,
        "employee_id": employee_id, "department_id": academic_setup["department_id"],
        "subject": "Data Structures", "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _make_student(admin_client, academic_setup, email):
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": "S " + email, "email": email,
        "admission_date": "2025-09-01",
        "program_id": academic_setup["program_id"],
        "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"],
        "academic_session_id": academic_setup["session_id"],
        "password": "Student!2025",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Admin sets a teacher's password on edit ──────────────────────────────────
async def test_admin_sets_teacher_password_on_edit(admin_client, academic_setup, client):
    teacher = await _make_teacher(admin_client, academic_setup, "pw.t@test.edu", "EMP-PW-1")
    # NB: admin_client and client share cookies, so do ALL admin operations
    # FIRST (before any login_as that would replace the admin session).
    # Admin sets a NEW password directly on edit.
    patch = await admin_client.patch(f"/api/v1/teachers/{teacher['id']}", json={
        "password": "NewTeacher!2026",
    })
    assert patch.status_code == 200, patch.text
    # The OLD password no longer works (a 401 sets no cookie, so the admin
    # session on the shared client is preserved through this check).
    bad = await client.post("/api/v1/auth/login", json={
        "email": "pw.t@test.edu", "password": "Teacher!2025",
    })
    assert bad.status_code == 401
    # The NEW password works (this logs the teacher in — admin work is done).
    await login_as(client, "pw.t@test.edu", "NewTeacher!2026")


async def test_admin_sets_student_password_on_edit(admin_client, academic_setup, client):
    student = await _make_student(admin_client, academic_setup, "pw.s@test.edu")
    # Admin sets a NEW password directly on edit.
    patch = await admin_client.patch(f"/api/v1/students/{student['id']}", json={
        "password": "NewStudent!2026",
    })
    assert patch.status_code == 200, patch.text
    # The original no longer works; the new one does.
    bad = await client.post("/api/v1/auth/login", json={
        "email": "pw.s@test.edu", "password": "Student!2025",
    })
    assert bad.status_code == 401
    await login_as(client, "pw.s@test.edu", "NewStudent!2026")


async def test_edit_without_password_keeps_current(admin_client, academic_setup, client):
    teacher = await _make_teacher(admin_client, academic_setup, "keep.t@test.edu", "EMP-KEEP-1")
    # Edit only the subject — no password field.
    patch = await admin_client.patch(f"/api/v1/teachers/{teacher['id']}", json={
        "subject": "Calculus",
    })
    assert patch.status_code == 200, patch.text
    # The original password still works.
    await login_as(client, "keep.t@test.edu", "Teacher!2025")


async def test_weak_password_on_edit_rejected_4xx(admin_client, academic_setup):
    teacher = await _make_teacher(admin_client, academic_setup, "weak.t@test.edu", "EMP-WEAK-1")
    resp = await admin_client.patch(f"/api/v1/teachers/{teacher['id']}", json={
        "password": "short",
    })
    assert resp.status_code in (400, 422), resp.text
    assert resp.status_code != 500


# ── Admin creation ───────────────────────────────────────────────────────────
async def test_admin_creates_another_admin(admin_client, client):
    resp = await admin_client.post("/api/v1/auth/admins", json={
        "email": "new.admin@test.edu", "full_name": "New Admin",
        "phone": "0300-1234567", "password": "Admin!2026",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "admin"
    assert body["is_active"] is True
    assert body["must_reset_password"] is False
    # The new admin can log in immediately with the chosen password.
    await login_as(client, "new.admin@test.edu", "Admin!2026")


async def test_non_admin_cannot_create_admin_via_teacher(admin_client, academic_setup, client):
    await _make_teacher(admin_client, academic_setup, "forbidden.t@test.edu", "EMP-FORB-1")
    teacher_client = await login_as(client, "forbidden.t@test.edu", "Teacher!2025")
    resp = await teacher_client.post("/api/v1/auth/admins", json={
        "email": "sneaky@test.edu", "full_name": "Sneaky", "password": "Admin!2026",
    })
    assert resp.status_code == 403


async def test_duplicate_admin_email_rejected(admin_client):
    # The seed admin already exists; reuse its email.
    resp = await admin_client.post("/api/v1/auth/admins", json={
        "email": "admin@test.edu", "full_name": "Dup", "password": "Admin!2026",
    })
    assert resp.status_code == 409


async def test_list_admins(admin_client):
    # Create a second admin, then list.
    created = await admin_client.post("/api/v1/auth/admins", json={
        "email": "second.admin@test.edu", "full_name": "Second Admin",
        "password": "Admin!2026",
    })
    assert created.status_code == 201
    resp = await admin_client.get("/api/v1/auth/admins")
    assert resp.status_code == 200, resp.text
    emails = {u["email"] for u in resp.json()}
    assert "admin@test.edu" in emails
    assert "second.admin@test.edu" in emails
    assert all(u["role"] == "admin" for u in resp.json())
