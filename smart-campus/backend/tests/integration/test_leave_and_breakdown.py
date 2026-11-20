"""Integration: leave records (student + teacher) and attendance breakdown
(present / absent / leave donut data)."""
from datetime import date, timedelta

from tests.conftest import login_as
from tests.integration.test_attendance_workflow import _make_timetable_entry, _setup_teacher
from tests.integration.test_student_workflow import _create_student

_WEEKDAY = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


# ---------------- Leave submission ----------------
async def test_student_leave_submission(admin_client, academic_setup):
    student = await _create_student(admin_client, academic_setup, email="leave.s1@test.edu")
    resp = await admin_client.post("/api/v1/leave", json={
        "person_type": "student", "student_id": student["id"],
        "start_date": "2025-09-01", "end_date": "2025-09-03", "reason": "Medical leave",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["person_type"] == "student"
    assert body["status"] == "approved"
    assert body["approved_by"]
    hist = await admin_client.get(f"/api/v1/leave/student/{student['id']}")
    assert hist.status_code == 200
    assert len(hist.json()) == 1


async def test_teacher_leave_submission(admin_client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup)
    resp = await admin_client.post("/api/v1/leave", json={
        "person_type": "teacher", "teacher_id": teacher["id"],
        "start_date": "2025-09-01", "end_date": "2025-09-02", "reason": "Personal leave",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["person_type"] == "teacher"
    hist = await admin_client.get(f"/api/v1/leave/teacher/{teacher['id']}")
    assert len(hist.json()) == 1


async def test_leave_invalid_date_range(admin_client, academic_setup):
    student = await _create_student(admin_client, academic_setup, email="leave.s2@test.edu")
    resp = await admin_client.post("/api/v1/leave", json={
        "person_type": "student", "student_id": student["id"],
        "start_date": "2025-09-05", "end_date": "2025-09-01", "reason": "Bad range",
    })
    assert resp.status_code == 422


async def test_leave_reason_too_short(admin_client, academic_setup):
    student = await _create_student(admin_client, academic_setup, email="leave.s3@test.edu")
    resp = await admin_client.post("/api/v1/leave", json={
        "person_type": "student", "student_id": student["id"],
        "start_date": "2025-09-01", "end_date": "2025-09-02", "reason": "ab",
    })
    assert resp.status_code == 422


async def test_leave_nonexistent_person(admin_client, academic_setup):
    resp = await admin_client.post("/api/v1/leave", json={
        "person_type": "student", "student_id": "00000000-0000-0000-0000-000000000000",
        "start_date": "2025-09-01", "end_date": "2025-09-02", "reason": "Leave",
    })
    assert resp.status_code == 404


async def test_leave_non_admin_forbidden(admin_client, client, academic_setup):
    student = await _create_student(admin_client, academic_setup, email="leave.s4@test.edu")
    await login_as(client, "leave.s4@test.edu", "Student!2025")
    resp = await client.post("/api/v1/leave", json={
        "person_type": "student", "student_id": student["id"],
        "start_date": "2025-09-01", "end_date": "2025-09-02", "reason": "Leave",
    })
    assert resp.status_code == 403


async def test_leave_single_day_is_inclusive(admin_client, academic_setup):
    student = await _create_student(admin_client, academic_setup, email="leave.s5@test.edu")
    resp = await admin_client.post("/api/v1/leave", json={
        "person_type": "student", "student_id": student["id"],
        "start_date": "2025-09-01", "end_date": "2025-09-01", "reason": "One day leave",
    })
    assert resp.status_code == 200
    assert resp.json()["start_date"] == resp.json()["end_date"] == "2025-09-01"


# ---------------- Attendance breakdown ----------------
async def test_breakdown_empty(admin_client, academic_setup):
    student = await _create_student(admin_client, academic_setup, email="brk.s1@test.edu")
    resp = await admin_client.get(f"/api/v1/attendance/student/{student['id']}/breakdown")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["present"] == 0 and body["absent"] == 0 and body["leave"] == 0
    assert body["total_scheduled"] == 0
    assert body["percentage"] == 0.0


async def test_breakdown_counts_present_absent_leave(admin_client, client, academic_setup):
    teacher = await _setup_teacher(admin_client, academic_setup)
    student = await _create_student(admin_client, academic_setup, email="brk.s2@test.edu")
    # A Monday lecture (Aug 4 2025 is a Monday, within the 2025-2026 session).
    resp = await admin_client.post("/api/v1/timetable/entries", json={
        "academic_session_id": academic_setup["session_id"], "day_of_week": "monday",
        "start_time": "08:30", "end_time": "09:30",
        "subject_id": academic_setup["subject_id"], "teacher_id": teacher["id"],
        "class_id": academic_setup["class_id"], "section_id": academic_setup["section_id"],
        "classroom_id": academic_setup["classroom_id"],
    })
    assert resp.status_code == 200, resp.text
    entry = resp.json()

    # Submit leave as admin FIRST (admin_client and client share one session,
    # so we must submit before logging in as the teacher). Leave covers a
    # different Monday (2025-09-22) — an unmarked scheduled session -> leave.
    leave = await admin_client.post("/api/v1/leave", json={
        "person_type": "student", "student_id": student["id"],
        "start_date": "2025-09-22", "end_date": "2025-09-22", "reason": "Medical leave",
    })
    assert leave.status_code == 200, leave.text

    # Mark the student present on 2025-09-15 (Monday) as the teacher.
    await login_as(client, "teacher.t1@test.edu", "Teacher!2025")
    mark = await client.post("/api/v1/attendance/mark", json={
        "timetable_entry_id": entry["id"], "attendance_date": "2025-09-15",
        "marks": [{"student_id": student["id"], "status": "present"}],
    })
    assert mark.status_code == 200, mark.text

    brk = await client.get(f"/api/v1/attendance/student/{student['id']}/breakdown")
    assert brk.status_code == 200, brk.text
    b = brk.json()
    assert b["present"] == 1
    assert b["leave"] >= 1
    assert b["total_scheduled"] == b["present"] + b["absent"] + b["leave"]


# ---------------- Dashboards ----------------
async def test_admin_dashboard_no_attendance_panel(admin_client, academic_setup):
    resp = await admin_client.get("/api/v1/dashboard/admin")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "attendance_trend" not in body
    for key in ("fee_collection_trend", "class_comparison", "program_distribution", "examination_performance"):
        assert key in body
    labels = [s["label"] for s in body["stats"]]
    for expected in ("Total Students", "Total Teachers", "Active Classes", "Total Sections",
                     "Fee Collection", "Outstanding Fees"):
        assert expected in labels


async def test_teacher_dashboard_weekly_and_distribution(admin_client, client, academic_setup):
    await _setup_teacher(admin_client, academic_setup)
    await login_as(client, "teacher.t1@test.edu", "Teacher!2025")
    resp = await client.get("/api/v1/dashboard/teacher")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body["weekly_timetable"], list)
    assert "class_distribution" in body
    assert "student_performance" in body


async def test_student_dashboard_has_breakdown_and_lectures(admin_client, client, academic_setup):
    student = await _create_student(admin_client, academic_setup, email="dash.s1@test.edu")
    await login_as(client, "dash.s1@test.edu", "Student!2025")
    resp = await client.get("/api/v1/dashboard/student")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "attendance_breakdown" in body
    for k in ("present", "absent", "leave", "total_scheduled", "percentage"):
        assert k in body["attendance_breakdown"]
    assert "lecture_overview" in body
