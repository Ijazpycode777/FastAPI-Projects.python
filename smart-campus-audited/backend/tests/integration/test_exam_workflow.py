"""Integration: examination creation, marks entry, finalize, and policy-version invariance."""
from datetime import date


async def _policy(admin_client):
    resp = await admin_client.post("/api/v1/grading", json={
        "name": "Std", "description": "5-band",
        "boundaries": [
            {"grade_name": "F", "min_percentage": 0, "max_percentage": 40, "is_pass": False},
            {"grade_name": "C", "min_percentage": 40, "max_percentage": 50, "is_pass": True},
            {"grade_name": "B", "min_percentage": 50, "max_percentage": 70, "is_pass": True},
            {"grade_name": "A", "min_percentage": 70, "max_percentage": 85, "is_pass": True},
            {"grade_name": "A+", "min_percentage": 85, "max_percentage": 100, "is_pass": True},
        ],
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _student(admin_client, setup, email):
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": "Stu Exam", "email": email, "admission_date": "2025-08-01",
        "program_id": setup["program_id"], "class_id": setup["class_id"],
        "section_id": setup["section_id"], "academic_session_id": setup["session_id"],
        "password": "Student!2025",
    })
    return resp.json()


async def test_exam_marks_finalize_and_grade(admin_client, academic_setup):
    policy = await _policy(admin_client)
    s1 = await _student(admin_client, academic_setup, "student.ex1@test.edu")
    s2 = await _student(admin_client, academic_setup, "student.ex2@test.edu")
    exam = await admin_client.post("/api/v1/examinations", json={
        "name": "Midterm", "exam_type": "midterm",
        "academic_session_id": academic_setup["session_id"],
        "program_id": academic_setup["program_id"], "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"], "subject_id": academic_setup["subject_id"],
        "max_marks": 100, "passing_marks": 40, "exam_date": "2025-10-15",
        "grading_policy_id": policy["id"],
    })
    assert exam.status_code == 200, exam.text
    eid = exam.json()["id"]
    marks = await admin_client.post(f"/api/v1/examinations/{eid}/marks", json={
        "entries": [
            {"student_id": s1["id"], "marks_obtained": 85, "is_absent": False},
            {"student_id": s2["id"], "marks_obtained": 0, "is_absent": True},
        ],
    })
    assert marks.status_code == 200, marks.text
    rows = {r["student_id"]: r for r in marks.json()}
    assert rows[s1["id"]]["grade"] == "A+"   # 85% lands in the [85,100] band
    assert rows[s1["id"]]["is_pass"] is True
    assert rows[s2["id"]]["is_absent"] is True
    assert rows[s2["id"]]["is_pass"] is False
    # Publish then finalize.
    assert (await admin_client.post(f"/api/v1/examinations/{eid}/publish")).status_code == 200
    fin = await admin_client.post(f"/api/v1/examinations/{eid}/finalize")
    assert fin.status_code == 200
    assert fin.json()["status"] == "finalized"


async def test_finalized_results_unchanged_after_policy_update(admin_client, academic_setup):
    """Changing grading policy for future exams must not rewrite historical results."""
    policy = await _policy(admin_client)
    s1 = await _student(admin_client, academic_setup, "student.ex3@test.edu")
    exam = await admin_client.post("/api/v1/examinations", json={
        "name": "Final", "exam_type": "final",
        "academic_session_id": academic_setup["session_id"],
        "program_id": academic_setup["program_id"], "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"], "subject_id": academic_setup["subject_id"],
        "max_marks": 100, "passing_marks": 40, "exam_date": "2025-12-10",
        "grading_policy_id": policy["id"],
    })
    eid = exam.json()["id"]
    await admin_client.post(f"/api/v1/examinations/{eid}/marks", json={
        "entries": [{"student_id": s1["id"], "marks_obtained": 75, "is_absent": False}],
    })
    await admin_client.post(f"/api/v1/examinations/{eid}/publish")
    await admin_client.post(f"/api/v1/examinations/{eid}/finalize")

    before = (await admin_client.get(f"/api/v1/examinations/{eid}/marks")).json()
    grade_before = before[0]["grade"]

    # Create a NEW policy version and activate it.
    new_policy = await admin_client.post("/api/v1/grading", json={
        "name": "Std", "description": "revised",
        "boundaries": [
            {"grade_name": "F", "min_percentage": 0, "max_percentage": 50, "is_pass": False},
            {"grade_name": "P", "min_percentage": 50, "max_percentage": 100, "is_pass": True},
        ],
    })
    await admin_client.post(f"/api/v1/grading/{new_policy.json()['id']}/activate")

    after = (await admin_client.get(f"/api/v1/examinations/{eid}/marks")).json()
    assert after[0]["grade"] == grade_before  # unchanged
    assert after[0]["percentage"] == before[0]["percentage"]


async def test_marks_exceeding_max_rejected(admin_client, academic_setup):
    policy = await _policy(admin_client)
    s1 = await _student(admin_client, academic_setup, "student.ex4@test.edu")
    exam = await admin_client.post("/api/v1/examinations", json={
        "name": "Quiz", "exam_type": "quiz",
        "academic_session_id": academic_setup["session_id"],
        "program_id": academic_setup["program_id"], "class_id": academic_setup["class_id"],
        "section_id": academic_setup["section_id"], "subject_id": academic_setup["subject_id"],
        "max_marks": 50, "passing_marks": 20, "exam_date": "2025-11-01",
        "grading_policy_id": policy["id"],
    })
    eid = exam.json()["id"]
    resp = await admin_client.post(f"/api/v1/examinations/{eid}/marks", json={
        "entries": [{"student_id": s1["id"], "marks_obtained": 60, "is_absent": False}],
    })
    assert resp.status_code in (400, 403, 422)
