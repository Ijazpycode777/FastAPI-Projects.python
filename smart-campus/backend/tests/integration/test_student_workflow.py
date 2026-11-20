"""Integration: student creation, self-access, and unauthorized access."""
from tests.conftest import login_as


async def _create_student(admin_client, setup, email="student.s1@test.edu", n=1):
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": "Student One", "email": email, "phone": "+923000000001",
        "date_of_birth": "2007-03-15", "gender": "male",
        "admission_date": "2025-08-01",
        "program_id": setup["program_id"], "class_id": setup["class_id"],
        "section_id": setup["section_id"], "academic_session_id": setup["session_id"],
        "password": "Student!2025",
        "guardian": {"name": "Mr One", "phone": "+923001110001", "relationship_type": "Father"},
        "matric_board": "BISE Lahore", "matric_year": 2023,
        "matric_total": 1100, "matric_obtained": 950, "matric_grade": "A",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_admin_creates_student_persisted(admin_client, academic_setup):
    student = await _create_student(admin_client, academic_setup)
    assert student["admission_number"].startswith("SC-")
    assert student["account_status"] == "active"
    # Fetched back -> persisted.
    fetched = await admin_client.get(f"/api/v1/students/{student['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["email"] == student["email"]


async def test_student_logs_in_and_accesses_dashboard(admin_client, client, academic_setup):
    student = await _create_student(admin_client, academic_setup, email="student.s2@test.edu")
    await login_as(client, "student.s2@test.edu", "Student!2025")
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["role"] == "student"
    dash = await client.get("/api/v1/dashboard/student")
    assert dash.status_code == 200
    assert "attendance_percentage" in dash.json()


async def test_student_cannot_view_another_student(admin_client, client, academic_setup):
    s1 = await _create_student(admin_client, academic_setup, email="student.a@test.edu")
    s2 = await _create_student(admin_client, academic_setup, email="student.b@test.edu")
    await login_as(client, "student.a@test.edu", "Student!2025")
    # s1 tries to read s2's board records -> forbidden
    resp = await client.get(f"/api/v1/students/{s2['id']}/board-records")
    assert resp.status_code == 403


async def test_unauthenticated_cannot_list_students(client):
    resp = await client.get("/api/v1/students")
    assert resp.status_code == 401


async def test_student_cannot_access_admin_reports(admin_client, client, academic_setup):
    await _create_student(admin_client, academic_setup, email="student.c@test.edu")
    await login_as(client, "student.c@test.edu", "Student!2025")
    resp = await client.get("/api/v1/students?page=1")
    assert resp.status_code == 403
