"""Integration: teacher creation, assignment, attendance marking & percentage."""
from datetime import date

from tests.conftest import login_as


async def _setup_teacher(admin_client, setup, email="teacher.t1@test.edu"):
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": "Teacher One", "email": email, "phone": "+923000000010",
        "employee_id": "EMP-T1", "department": "CS", "designation": "Lecturer",
        "joining_date": "2022-09-01", "password": "Teacher!2025",
    })
    assert resp.status_code == 200, resp.text
    teacher = resp.json()
    # Assign teacher to subject+class+section
    a = await admin_client.post("/api/v1/assignments", json={
        "teacher_id": teacher["id"], "subject_id": setup["subject_id"],
        "class_id": setup["class_id"], "section_id": setup["section_id"],
        "academic_session_id": setup["session_id"],
    })
    assert a.status_code == 200, a.text
    return teacher


async def _create_student(admin_client, setup, email, n=1):
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": "Stu", "email": email, "admission_date": "2025-08-01",
        "campus_shift_id": setup["shift_id"], "roll_number": n,
        "program": setup["program_name"], "class_name": setup["class_name"],
        "section": setup["section_name"], "academic_session": setup["session_name"],
        "password": "Student!2025",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _make_timetable_entry(admin_client, setup, teacher_id):
    today_name = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][date.today().weekday()]
    resp = await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": setup["session_id"], "day_of_week": today_name,
        "start_time": "08:30", "end_time": "09:30",
        "subject_id": setup["subject_id"], "teacher_id": teacher_id,
        "class_id": setup["class_id"], "section_id": setup["section_id"],
        "classroom_id": setup["classroom_id"],
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_teacher_marks_attendance_and_percentage(admin_client, client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup)
    student = await _create_student(admin_client, academic_setup, "student.att1@test.edu")
    entry = await _make_timetable_entry(admin_client, academic_setup, teacher["id"])

    await login_as(client, "teacher.t1@test.edu", "Teacher!2025")
    mark = await client.post("/api/v1/attendance/mark", json={
        "timetable_entry_id": entry["id"],
        "attendance_date": str(date.today()),
        "marks": [
            {"student_id": student["id"], "status": "present"},
        ],
    })
    assert mark.status_code == 200, mark.text
    # Percentage should be 100 for present.
    pct = await client.get(f"/api/v1/attendance/student/{student['id']}")
    assert pct.status_code == 200
    assert pct.json()["percentage"] == 100.0


async def test_duplicate_attendance_rejected(admin_client, client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup)
    student = await _create_student(admin_client, academic_setup, "student.att2@test.edu")
    entry = await _make_timetable_entry(admin_client, academic_setup, teacher["id"])
    await login_as(client, "teacher.t1@test.edu", "Teacher!2025")
    payload = {
        "timetable_entry_id": entry["id"],
        "attendance_date": str(date.today()),
        "marks": [{"student_id": student["id"], "status": "present"}],
    }
    first = await client.post("/api/v1/attendance/mark", json=payload)
    assert first.status_code == 200
    second = await client.post("/api/v1/attendance/mark", json=payload)
    assert second.status_code == 409


async def test_teacher_checkin_checkout(admin_client, client, academic_setup):
    await _setup_teacher(admin_client, academic_setup, email="teacher.t2@test.edu")
    await login_as(client, "teacher.t2@test.edu", "Teacher!2025")
    ci = await client.post("/api/v1/teacher-attendance/check-in")
    assert ci.status_code == 200, ci.text
    # Second check-in same day -> conflict.
    again = await client.post("/api/v1/teacher-attendance/check-in")
    assert again.status_code == 409
    co = await client.post("/api/v1/teacher-attendance/check-out")
    assert co.status_code == 200
    assert co.json()["work_minutes"] >= 0
