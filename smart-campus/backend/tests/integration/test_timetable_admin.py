"""Integration: timetable administration — create, edit, delete, conflicts."""
from tests.conftest import login_as
from tests.integration.test_attendance_workflow import _setup_teacher
from tests.integration.test_student_workflow import _create_student


async def _entry(admin_client, setup, teacher_id, day, start, end):
    return await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": setup["session_id"], "day_of_week": day,
        "start_time": start, "end_time": end,
        "subject_id": setup["subject_id"], "teacher_id": teacher_id,
        "class_id": setup["class_id"], "section_id": setup["section_id"],
        "classroom_id": setup["classroom_id"],
    })


async def test_admin_creates_timetable_entry(admin_client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup)
    resp = await _entry(admin_client, academic_setup, teacher["id"], "monday", "08:30", "09:30")
    assert resp.status_code == 200, resp.text
    assert resp.json()["day_of_week"] == "monday"


async def test_timetable_conflict_rejected(admin_client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup)
    r1 = await _entry(admin_client, academic_setup, teacher["id"], "monday", "08:30", "09:30")
    assert r1.status_code == 200, r1.text
    # Same teacher, same day, overlapping time -> conflict.
    r2 = await _entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    assert r2.status_code == 409
    assert "already" in r2.json()["error"]["message"].lower()


async def test_admin_edits_entry_and_conflict_on_edit(admin_client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup)
    e = (await _entry(admin_client, academic_setup, teacher["id"], "tuesday", "10:00", "11:00")).json()
    patch = await admin_client.patch(f"/api/v1/timetable/entries/{e['id']}", json={"start_time": "11:00", "end_time": "12:00"})
    assert patch.status_code == 200, patch.text
    assert patch.json()["start_time"] == "11:00:00"
    # Create a second entry in a non-overlapping slot, then edit e INTO it -> 409.
    await _entry(admin_client, academic_setup, teacher["id"], "tuesday", "13:00", "14:00")
    bad = await admin_client.patch(f"/api/v1/timetable/entries/{e['id']}", json={"start_time": "13:30", "end_time": "14:30"})
    assert bad.status_code == 409


async def test_admin_deletes_entry(admin_client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup)
    e = (await _entry(admin_client, academic_setup, teacher["id"], "wednesday", "08:30", "09:30")).json()
    dele = await admin_client.delete(f"/api/v1/timetable/entries/{e['id']}")
    assert dele.status_code == 204
    rows = (await admin_client.get("/api/v1/timetable/entries", params={"class_id": academic_setup["class_id"]})).json()
    assert all(r["id"] != e["id"] for r in rows)


async def test_student_cannot_create_entry(admin_client, client, academic_setup):
    await _create_student(admin_client, academic_setup, email="tt.s1@test.edu")
    await login_as(client, "tt.s1@test.edu", "Student!2025")
    resp = await client.post("/api/v1/timetable/entries", json={
        "academic_session_id": academic_setup["session_id"], "day_of_week": "monday",
        "start_time": "08:30", "end_time": "09:30", "subject_id": academic_setup["subject_id"],
        "teacher_id": "00000000-0000-0000-0000-000000000000", "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"],
    })
    assert resp.status_code == 403
