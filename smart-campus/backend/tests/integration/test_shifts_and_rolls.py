"""Integration: campus shifts + roll-number architecture (Stage 1)."""
from tests.conftest import login_as
from tests.integration.test_student_workflow import _create_student


async def _shift(client, name, code):
    r = await client.post("/api/v1/campus/shifts", json={
        "name": name, "code": code, "is_active": True,
    })
    assert r.status_code == 200, r.text
    return r.json()


async def test_shift_create_list_update_and_duplicate(admin_client, academic_setup):
    # academic_setup already creates a Morning shift.
    ev = await _shift(admin_client, "Evening", "EVE")
    shifts = (await admin_client.get("/api/v1/campus/shifts")).json()
    codes = {s["code"] for s in shifts}
    assert {"MORNING", "EVE"}.issubset(codes)
    # Duplicate code rejected.
    dup = await admin_client.post("/api/v1/campus/shifts", json={"name": "Eve2", "code": "EVE"})
    assert dup.status_code == 409
    # Update.
    patch = await admin_client.patch(f"/api/v1/campus/shifts/{ev['id']}", json={"is_active": False})
    assert patch.status_code == 200
    assert patch.json()["is_active"] is False


async def test_student_has_shift_and_detail_name(admin_client, academic_setup):
    s = await _create_student(admin_client, academic_setup, email="shift.s1@test.edu")
    detail = (await admin_client.get(f"/api/v1/students/{s['id']}")).json()
    assert detail["campus_shift_id"] == academic_setup["shift_id"]
    assert detail["campus_shift_name"] == "Morning"


async def test_duplicate_roll_within_shift_rejected(admin_client, academic_setup):
    await _create_student(admin_client, academic_setup, email="dup.s1@test.edu", n=1)
    dup = await admin_client.post("/api/v1/students", json={
        "full_name": "Dup Two", "email": "dup.s2@test.edu", "admission_date": "2025-08-01",
        "campus_shift_id": academic_setup["shift_id"], "roll_number": 1,
        "program": academic_setup["program_name"], "class_name": academic_setup["class_name"],
        "section": academic_setup["section_name"], "academic_session": academic_setup["session_name"],
        "password": "Student!2025",
    })
    assert dup.status_code == 409
    assert "roll" in dup.json()["error"]["message"].lower()


async def test_reuse_roll_across_different_shifts(admin_client, academic_setup):
    # Morning student with roll 1.
    await _create_student(admin_client, academic_setup, email="cross.s1@test.edu", n=1)
    evening = await _shift(admin_client, "Evening", "EVE")
    # Same roll 1 in the Evening shift must be permitted.
    r = await admin_client.post("/api/v1/students", json={
        "full_name": "Cross Two", "email": "cross.s2@test.edu", "admission_date": "2025-08-01",
        "campus_shift_id": evening["id"], "roll_number": 1,
        "program": academic_setup["program_name"], "class_name": academic_setup["class_name"],
        "section": academic_setup["section_name"], "academic_session": academic_setup["session_name"],
        "password": "Student!2025",
    })
    assert r.status_code == 200, r.text
    assert r.json()["campus_shift_id"] == evening["id"]


async def test_roll_scheme_range_validation(admin_client, academic_setup):
    # Configure a scheme: rolls 100-200 for Morning / this class.
    scheme = await admin_client.post("/api/v1/campus/roll-schemes", json={
        "campus_shift_id": academic_setup["shift_id"], "class_id": academic_setup["class_id"],
        "prefix": "ICS1", "min_roll": 100, "max_roll": 200, "padding": 3,
    })
    assert scheme.status_code == 200, scheme.text
    # Roll outside the range -> rejected.
    bad = await admin_client.post("/api/v1/students", json={
        "full_name": "Range Bad", "email": "range.bad@test.edu", "admission_date": "2025-08-01",
        "campus_shift_id": academic_setup["shift_id"], "roll_number": 5,
        "program": academic_setup["program_name"], "class_name": academic_setup["class_name"],
        "section": academic_setup["section_name"], "academic_session": academic_setup["session_name"],
        "password": "Student!2025",
    })
    assert bad.status_code == 422
    assert "outside" in bad.json()["error"]["message"].lower()
    # Roll within the range -> accepted.
    ok = await admin_client.post("/api/v1/students", json={
        "full_name": "Range Ok", "email": "range.ok@test.edu", "admission_date": "2025-08-01",
        "campus_shift_id": academic_setup["shift_id"], "roll_number": 150,
        "program": academic_setup["program_name"], "class_name": academic_setup["class_name"],
        "section": academic_setup["section_name"], "academic_session": academic_setup["session_name"],
        "password": "Student!2025",
    })
    assert ok.status_code == 200, ok.text
    # Scheme CRUD: update + delete.
    patch = await admin_client.patch(f"/api/v1/campus/roll-schemes/{scheme.json()['id']}", json={"max_roll": 250})
    assert patch.status_code == 200 and patch.json()["max_roll"] == 250
    dele = await admin_client.delete(f"/api/v1/campus/roll-schemes/{scheme.json()['id']}")
    assert dele.status_code == 204


async def test_roll_search_and_shift_filter(admin_client, academic_setup):
    s = await _create_student(admin_client, academic_setup, email="find.s1@test.edu", n=42)
    # Search by roll number.
    by_roll = (await admin_client.get("/api/v1/students?q=42")).json()
    assert any(st["id"] == s["id"] for st in by_roll["items"])
    # Filter by campus shift.
    by_shift = (await admin_client.get(f"/api/v1/students?campus_shift_id={academic_setup['shift_id']}")).json()
    assert any(st["id"] == s["id"] for st in by_shift["items"])


async def test_roll_change_preserves_uuid_and_frees_roll(admin_client, academic_setup):
    s = await _create_student(admin_client, academic_setup, email="change.s1@test.edu", n=1)
    uid = s["id"]
    patch = await admin_client.patch(f"/api/v1/students/{uid}", json={"roll_number": 99})
    assert patch.status_code == 200, patch.text
    assert patch.json()["id"] == uid  # UUID unchanged
    assert patch.json()["current_roll_number"] == 99
    # Roll 1 is now free in this shift -> reusable by a new student.
    again = await _create_student(admin_client, academic_setup, email="change.s2@test.edu", n=1)
    assert again["current_roll_number"] == 1


async def test_promote_requires_and_validates_roll(admin_client, academic_setup):
    s = await _create_student(admin_client, academic_setup, email="promote.s1@test.edu", n=1)
    # Missing new_roll_number -> schema 422.
    bad = await admin_client.post("/api/v1/students/promote", json={
        "student_id": s["id"], "new_academic_session_id": academic_setup["session_id"],
        "new_class_id": academic_setup["class_id"], "new_section_id": academic_setup["section_id"],
    })
    assert bad.status_code == 422
    # With a new roll -> 200.
    ok = await admin_client.post("/api/v1/students/promote", json={
        "student_id": s["id"], "new_academic_session_id": academic_setup["session_id"],
        "new_class_id": academic_setup["class_id"], "new_section_id": academic_setup["section_id"],
        "new_roll_number": 77, "action": "promoted",
    })
    assert ok.status_code == 200, ok.text
    assert ok.json()["current_roll_number"] == 77


async def test_non_admin_cannot_manage_shifts(admin_client, client, academic_setup):
    s = await _create_student(admin_client, academic_setup, email="forbid.s1@test.edu")
    await login_as(client, "forbid.s1@test.edu", "Student!2025")
    r = await client.post("/api/v1/campus/shifts", json={"name": "X", "code": "X"})
    assert r.status_code == 403
    schemes = await client.get("/api/v1/campus/roll-schemes")
    assert schemes.status_code == 403


async def test_student_logs_filters_combine(admin_client, academic_setup):
    s = await _create_student(admin_client, academic_setup, email="log.s1@test.edu", n=3)
    # All filters together: shift + class + section + session + status.
    rows = (await admin_client.get("/api/v1/students", params={
        "campus_shift_id": academic_setup["shift_id"],
        "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"],
        "session_id": academic_setup["session_id"],
        "status": "active",
    })).json()
    assert any(st["id"] == s["id"] for st in rows["items"])
    # Sorting by roll ascending.
    asc = (await admin_client.get("/api/v1/students?sort=roll&order=asc")).json()
    rolls = [st["current_roll_number"] for st in asc["items"] if st["current_roll_number"] is not None]
    assert rolls == sorted(rolls)


async def test_shift_accepts_empty_string_times(admin_client, academic_setup):
    """A shift created without picking times (empty strings) is accepted, stored as null."""
    r = await admin_client.post("/api/v1/campus/shifts", json={
        "name": "Weekend", "code": "WKND", "start_time": "", "end_time": "", "is_active": True,
    })
    assert r.status_code == 200, r.text
    assert r.json()["start_time"] is None
    assert r.json()["end_time"] is None
