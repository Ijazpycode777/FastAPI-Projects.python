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
    s1 = await _create_student(admin_client, academic_setup, email="student.a@test.edu", n=1)
    s2 = await _create_student(admin_client, academic_setup, email="student.b@test.edu", n=2)
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


async def test_student_create_rejects_unknown_placement_ids(admin_client, academic_setup):
    """ID-based placement never auto-creates rows: an unknown class_id is
    rejected with a 404 (the admin must first create the class on the Classes
    Distribution page). This is the fix for the old 'PB 21' vs 'Pb 21' split —
    there is no longer any free-text find-or-create."""
    bogus = "00000000-0000-0000-0000-000000000000"
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": "Bad Id", "email": "badid.s@test.edu",
        "admission_date": "2025-08-01",
        "program_id": academic_setup["program_id"], "class_id": bogus,
        "section_id": academic_setup["section_id"], "academic_session_id": academic_setup["session_id"],
        "password": "Student!2025",
    })
    assert resp.status_code == 404, resp.text
    assert "class" in resp.json()["error"]["message"].lower()

    # A class that exists but belongs to a DIFFERENT program is a 422 (wrong parent).
    other_prog = await admin_client.post("/api/v1/programs", json={"code": "FSc", "name": "FSc"})
    assert other_prog.status_code == 200
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": "Bad Combo", "email": "badcombo.s@test.edu",
        "admission_date": "2025-08-01",
        "program_id": other_prog.json()["id"], "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"], "academic_session_id": academic_setup["session_id"],
        "password": "Student!2025",
    })
    assert resp.status_code == 422, resp.text


async def test_two_students_share_one_class_row(admin_client, academic_setup, db):
    """The core fix for 'PB 21' vs 'Pb 21': two students placed in the same
    class via its ID share exactly one ClassLevel row — no duplicates, no
    case/spacing variants. The class row is the canonical identity."""
    from app.models.academic import ClassLevel
    from sqlalchemy import func as sa_func, select as sa_select

    payload = {
        "admission_date": "2025-08-01",
        "program_id": academic_setup["program_id"], "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"], "academic_session_id": academic_setup["session_id"],
        "password": "Student!2025",
    }
    r1 = await admin_client.post("/api/v1/students", json={
        "full_name": "Share One", "email": "share.1@test.edu", **payload})
    assert r1.status_code == 200, r1.text
    r2 = await admin_client.post("/api/v1/students", json={
        "full_name": "Share Two", "email": "share.2@test.edu", **payload})
    assert r2.status_code == 200, r2.text

    # Both students point at the SAME class row (one ID), and there is still
    # exactly one class row for this program — no duplicate "PB 21"/"Pb 21".
    assert r1.json()["current_class_id"] == r2.json()["current_class_id"] == academic_setup["class_id"]
    n_classes = (await db.execute(
        sa_select(sa_func.count()).select_from(ClassLevel)
        .where(ClassLevel.program_id == academic_setup["program_id"])
    )).scalar_one()
    assert n_classes == 1


async def test_student_update_placement_by_id(admin_client, academic_setup):
    """Editing a student's placement via IDs moves them to the selected rows;
    a partial placement (only some of the four IDs) is rejected."""
    student = await _create_student(admin_client, academic_setup, email="edit.s@test.edu")

    # Build a brand-new placement (program/class/section/session) via the API.
    fsc = await admin_client.post("/api/v1/programs", json={"code": "FSc", "name": "FSc"})
    assert fsc.status_code == 200
    p2 = await admin_client.post("/api/v1/classes", json={
        "program_id": fsc.json()["id"], "name": "Part 2", "year": 2})
    assert p2.status_code == 200
    green = await admin_client.post("/api/v1/sections", json={
        "class_level_id": p2.json()["id"], "name": "Green", "capacity": 40})
    assert green.status_code == 200
    sess2 = await admin_client.post("/api/v1/sessions", json={
        "name": "2026-2027", "start_date": "2026-08-01", "end_date": "2027-05-31", "is_active": False})
    assert sess2.status_code == 200

    resp = await admin_client.patch(f"/api/v1/students/{student['id']}", json={
        "program_id": fsc.json()["id"], "class_id": p2.json()["id"],
        "section_id": green.json()["id"], "academic_session_id": sess2.json()["id"],
    })
    assert resp.status_code == 200, resp.text
    detail = (await admin_client.get(f"/api/v1/students/{student['id']}")).json()
    assert detail["program_name"] == "FSc"
    assert detail["class_name"] == "Part 2"
    assert detail["section_name"] == "Green"
    assert detail["session_name"] == "2026-2027"

    # Partial placement (only some of the four IDs) is a 422.
    bad = await admin_client.patch(f"/api/v1/students/{student['id']}", json={
        "class_id": p2.json()["id"],
    })
    assert bad.status_code == 422, bad.text
