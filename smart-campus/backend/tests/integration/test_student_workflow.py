"""Integration: student creation, self-access, and unauthorized access."""
from tests.conftest import login_as


async def _create_student(admin_client, setup, email="student.s1@test.edu", n=1):
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": "Student One", "email": email, "phone": "+923000000001",
        "date_of_birth": "2007-03-15", "gender": "male",
        "admission_date": "2025-08-01",
        "campus_shift_id": setup["shift_id"], "roll_number": n,
        "program": setup["program_name"], "class_name": setup["class_name"],
        "section": setup["section_name"], "academic_session": setup["session_name"],
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


async def test_student_create_freetext_find_or_creates_rows(admin_client, academic_setup):
    """Free-text placement with brand-new names creates the academic rows."""
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": "Free Text", "email": "freetext.s@test.edu",
        "admission_date": "2025-08-01",
        "campus_shift_id": academic_setup["shift_id"], "roll_number": 1,
        "program": "BSCS", "class_name": "Year 1", "section": "Blue",
        "academic_session": "2025-2026", "password": "Student!2025",
    })
    assert resp.status_code == 200, resp.text
    sid = resp.json()["id"]

    # The typed rows must now exist.
    progs = (await admin_client.get("/api/v1/programs")).json()
    assert any(p["name"] == "BSCS" for p in progs)
    sessions = (await admin_client.get("/api/v1/sessions")).json()
    assert any(s["name"] == "2025-2026" for s in sessions)

    # Detail must expose the resolved names (used to prefill the edit form).
    detail = (await admin_client.get(f"/api/v1/students/{sid}")).json()
    assert detail["program_name"] == "BSCS"
    assert detail["class_name"] == "Year 1"
    assert detail["section_name"] == "Blue"
    assert detail["session_name"] == "2025-2026"


async def test_student_create_freetext_reuses_existing_case_insensitive(admin_client, academic_setup):
    """Repeated / case-variant free-text placement reuses the same rows (no duplicates)."""
    payload = {
        "admission_date": "2025-08-01", "program": "ICS", "class_name": "Part 1",
        "section": "A", "academic_session": "2025-2026", "password": "Student!2025",
        "campus_shift_id": academic_setup["shift_id"],
    }
    r1 = await admin_client.post("/api/v1/students", json={
        "full_name": "Reuse One", "email": "reuse.1@test.edu", "roll_number": 1, **payload})
    assert r1.status_code == 200, r1.text
    # Same names, different case and surrounding whitespace -> must reuse, not duplicate.
    r2 = await admin_client.post("/api/v1/students", json={
        "full_name": "Reuse Two", "email": "reuse.2@test.edu", "roll_number": 2,
        "admission_date": "2025-08-01", "program": " ics ", "class_name": " part 1 ",
        "section": " a ", "academic_session": "2025-2026", "password": "Student!2025",
        "campus_shift_id": academic_setup["shift_id"]})
    assert r2.status_code == 200, r2.text

    progs = (await admin_client.get("/api/v1/programs")).json()
    ics = [p for p in progs if p["name"].lower() == "ics"]
    assert len(ics) == 1
    sessions = (await admin_client.get("/api/v1/sessions")).json()
    assert len([s for s in sessions if s["name"] == "2025-2026"]) == 1

    classes = (await admin_client.get("/api/v1/classes", params={"program_id": ics[0]["id"]})).json()
    p1 = [c for c in classes if c["name"].lower() == "part 1"]
    assert len(p1) == 1
    sections = (await admin_client.get("/api/v1/sections", params={"class_level_id": p1[0]["id"]})).json()
    assert len([s for s in sections if s["name"].lower() == "a"]) == 1


async def test_student_update_freetext_placement(admin_client, academic_setup):
    """Editing a student with free-text placement updates the resolved rows."""
    student = await _create_student(admin_client, academic_setup, email="edit.s@test.edu")
    # Change placement to a brand-new section in a new class/program/session.
    resp = await admin_client.patch(f"/api/v1/students/{student['id']}", json={
        "program": "FSc", "class_name": "Part 2", "section": "Green",
        "academic_session": "2026-2027",
    })
    assert resp.status_code == 200, resp.text
    detail = (await admin_client.get(f"/api/v1/students/{student['id']}")).json()
    assert detail["program_name"] == "FSc"
    assert detail["class_name"] == "Part 2"
    assert detail["section_name"] == "Green"
    assert detail["session_name"] == "2026-2027"
