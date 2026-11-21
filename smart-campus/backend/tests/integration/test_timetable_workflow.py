"""Integration: timetable conflict detection enforced by the backend."""
async def _setup_teacher(admin_client, setup, email="teacher.tt1@test.edu"):
    emp = "EMP-" + email.split("@")[0].split(".")[-1].upper()
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Teacher TT", "email": email, "employee_id": emp,
        "department_id": setup["department_id"], "subject": "Computer Science",
        "designation": "Lecturer", "joining_date": "2022-09-01",
        "password": "Teacher!2025",
    })
    teacher = resp.json()
    await admin_client.post("/api/v1/assignments", json={
        "teacher_id": teacher["id"], "subject_id": setup["subject_id"],
        "class_id": setup["class_id"], "section_id": setup["section_id"],
        "academic_session_id": setup["session_id"],
    })
    return teacher


async def test_teacher_double_booked_conflict_rejected(admin_client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup)
    first = await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": academic_setup["session_id"], "day_of_week": "monday",
        "start_time": "08:30", "end_time": "09:30",
        "subject_id": academic_setup["subject_id"], "teacher_id": teacher["id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
    })
    assert first.status_code == 200
    # Overlapping time (09:00-10:00) for same teacher -> conflict.
    conflict = await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": academic_setup["session_id"], "day_of_week": "monday",
        "start_time": "09:00", "end_time": "10:00",
        "subject_id": academic_setup["subject_id"], "teacher_id": teacher["id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
    })
    assert conflict.status_code == 409


async def test_class_double_booked_conflict_rejected(admin_client, academic_setup):
    """Same class, overlapping time, different teacher → class conflict.

    (Replaces the former classroom-double-book test — the classroom feature
    was removed; class-level conflict detection remains.)
    """
    teacher = await _setup_teacher(admin_client, academic_setup, email="teacher.tt2@test.edu")
    first = await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": academic_setup["session_id"], "day_of_week": "tuesday",
        "start_time": "08:30", "end_time": "09:30",
        "subject_id": academic_setup["subject_id"], "teacher_id": teacher["id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
    })
    assert first.status_code == 200
    teacher2 = await _setup_teacher(admin_client, academic_setup, email="teacher.tt3@test.edu")
    conflict = await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": academic_setup["session_id"], "day_of_week": "tuesday",
        "start_time": "09:00", "end_time": "10:00",
        "subject_id": academic_setup["subject_id"], "teacher_id": teacher2["id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
    })
    assert conflict.status_code == 409


async def test_non_overlapping_entry_accepted(admin_client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup, email="teacher.tt4@test.edu")
    e1 = await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": academic_setup["session_id"], "day_of_week": "wednesday",
        "start_time": "08:30", "end_time": "09:30",
        "subject_id": academic_setup["subject_id"], "teacher_id": teacher["id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
    })
    assert e1.status_code == 200
    e2 = await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": academic_setup["session_id"], "day_of_week": "wednesday",
        "start_time": "09:30", "end_time": "10:30",
        "subject_id": academic_setup["subject_id"], "teacher_id": teacher["id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
    })
    assert e2.status_code == 200


async def test_entry_created_without_classroom_field(admin_client, academic_setup):
    """The classroom field is no longer required (or even accepted) — an entry
    payload with no classroom_id must succeed. (Spec: remove classroom.)"""
    teacher = await _setup_teacher(admin_client, academic_setup, email="teacher.tt5@test.edu")
    resp = await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": academic_setup["session_id"], "day_of_week": "thursday",
        "start_time": "08:30", "end_time": "09:30",
        "subject_id": academic_setup["subject_id"], "teacher_id": teacher["id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
    })
    assert resp.status_code == 200, resp.text
    assert "classroom_id" not in resp.json()
