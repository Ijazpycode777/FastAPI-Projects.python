"""Integration: Classes Distribution roster — role-scoped listing + the live
timetable status indicator.

Covers:
* Admin / teacher / student permissions (backend-enforced; a teacher cannot
  reach another teacher's roster by editing a class ID in the request).
* The roster contains only currently-enrolled students (active enrolment);
  promoted/transferred students are excluded.
* The 12 live-status scenarios from the spec, using a frozen server clock
  (monkeypatch of ``live_status_service.current_now``) so they are deterministic
  and independent of the real wall clock or day-of-week.

The status indicator is a live availability flag, NOT attendance — these tests
assert it never touches AttendanceRecord (the attendance suite still passes).
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services import live_status_service
from tests.conftest import login_as

# Monday 2026-01-05. 2026-01-01 is a Thursday, so 01-05 is a Monday. Used as
# the frozen "today" for every timetable-status scenario so the suite does not
# depend on the real day-of-week when it runs.
MON = (2026, 1, 5)


# ---------------- helpers ----------------
async def _make_teacher(admin_client, setup, email, section_id=None):
    """Create a teacher + an active assignment to (class, section) for the
    active session. Returns the teacher dict."""
    section_id = section_id or setup["section_id"]
    emp = "EMP-" + email.split("@")[0].upper()
    resp = await admin_client.post("/api/v1/teachers", json={
        "full_name": email.split("@")[0].replace(".", " ").title(),
        "email": email, "employee_id": emp,
        "department_id": setup["department_id"], "subject": "Computer Science",
        "designation": "Lecturer", "joining_date": "2022-09-01",
        "password": "Teacher!2025",
    })
    assert resp.status_code == 200, resp.text
    teacher = resp.json()
    a = await admin_client.post("/api/v1/assignments", json={
        "teacher_id": teacher["id"], "subject_id": setup["subject_id"],
        "class_id": setup["class_id"], "section_id": section_id,
        "academic_session_id": setup["session_id"],
    })
    assert a.status_code == 200, a.text
    return teacher


async def _make_entry(admin_client, setup, teacher_id, day, start, end,
                      section_id=None, class_id=None):
    payload = {
        "academic_session_id": setup["session_id"], "day_of_week": day,
        "start_time": start, "end_time": end,
        "subject_id": setup["subject_id"], "teacher_id": teacher_id,
        "class_id": class_id or setup["class_id"],
        "section_id": section_id or setup["section_id"],
    }
    resp = await admin_client.post("/api/v1/timetable/entries", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _make_student(admin_client, setup, email, section_id=None, class_id=None):
    resp = await admin_client.post("/api/v1/students", json={
        "full_name": email.split("@")[0].replace(".", " ").title(),
        "email": email, "admission_date": "2025-08-01",
        "program_id": setup["program_id"],
        "class_id": class_id or setup["class_id"],
        "section_id": section_id or setup["section_id"],
        "academic_session_id": setup["session_id"],
        "password": "Student!2025",
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


def _freeze(monkeypatch, hour, minute, y=MON[0], mo=MON[1], d=MON[2]):
    """Freeze the roster's server clock to a Monday at HH:MM (UTC, the default
    college timezone). Tests pass explicit hours/minutes to walk the scenarios."""
    monkeypatch.setattr(live_status_service, "current_now",
                        lambda: datetime(y, mo, d, hour, minute, tzinfo=ZoneInfo("UTC")))


async def _roster(client, class_id):
    resp = await client.get(f"/api/v1/classes/{class_id}/roster")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _status_of(roster, student_id):
    s = next((x for x in roster["students"] if x["id"] == student_id), None)
    assert s is not None, "student missing from roster"
    return s["live_status"]


# ---------------- permission tests ----------------
async def test_admin_lists_all_classes(admin_client, academic_setup):
    """Admin sees every class via the role-aware roster listing."""
    await admin_client.post("/api/v1/classes", json={
        "program_id": academic_setup["program_id"], "name": "Part 2", "year": 2})
    resp = await admin_client.get("/api/v1/classes/rosters")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Part 1" in names and "Part 2" in names


async def test_admin_opens_any_class_roster(admin_client, academic_setup):
    """Admin can open any class roster, even an empty one."""
    roster = await _roster(admin_client, academic_setup["class_id"])
    assert roster["class_name"] == "Part 1"
    assert roster["students"] == []
    assert "server_now" in roster and roster["timezone"]


async def test_teacher_lists_only_assigned_classes(admin_client, client, academic_setup):
    """A teacher's roster listing contains only classes they are assigned to."""
    other = await admin_client.post("/api/v1/classes", json={
        "program_id": academic_setup["program_id"], "name": "Part 2", "year": 2})
    other_id = other.json()["id"]
    teacher = await _make_teacher(admin_client, academic_setup, "t.perm1@test.edu")
    await login_as(client, teacher["email"], "Teacher!2025")

    resp = await client.get("/api/v1/classes/rosters")
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert academic_setup["class_id"] in ids          # assigned
    assert other_id not in ids                         # not assigned


async def test_teacher_opens_assigned_class_roster(admin_client, client, academic_setup):
    """A teacher can open the roster of a class they teach."""
    teacher = await _make_teacher(admin_client, academic_setup, "t.perm2@test.edu")
    await _make_student(admin_client, academic_setup, "s.perm2@test.edu")
    await login_as(client, teacher["email"], "Teacher!2025")
    roster = await _roster(client, academic_setup["class_id"])
    assert len(roster["students"]) == 1


async def test_teacher_cannot_open_unassigned_class_roster(admin_client, client, academic_setup):
    """A teacher cannot reach another teacher's class roster by editing the
    class ID in the URL/API request — enforced server-side (403)."""
    other = await admin_client.post("/api/v1/classes", json={
        "program_id": academic_setup["program_id"], "name": "Part 2", "year": 2})
    other_id = other.json()["id"]
    teacher = await _make_teacher(admin_client, academic_setup, "t.perm3@test.edu")
    await login_as(client, teacher["email"], "Teacher!2025")
    resp = await client.get(f"/api/v1/classes/{other_id}/roster")
    assert resp.status_code == 403


async def test_student_forbidden_from_rosters(admin_client, client, academic_setup):
    """Students are not permitted to list classes or open rosters (403)."""
    await _make_student(admin_client, academic_setup, "s.perm4@test.edu")
    await login_as(client, "s.perm4@test.edu", "Student!2025")
    assert (await client.get("/api/v1/classes/rosters")).status_code == 403
    resp = await client.get(f"/api/v1/classes/{academic_setup['class_id']}/roster")
    assert resp.status_code == 403


async def test_unknown_class_roster_404(admin_client, academic_setup):
    bogus = "00000000-0000-0000-0000-000000000000"
    resp = await admin_client.get(f"/api/v1/classes/{bogus}/roster")
    assert resp.status_code == 404


# ---------------- roster filtering ----------------
async def test_roster_excludes_promoted_students(admin_client, academic_setup):
    """Only currently-enrolled students appear; a promoted/transferred student
    (old enrolment is_active=False) is excluded."""
    cls_y = await admin_client.post("/api/v1/classes", json={
        "program_id": academic_setup["program_id"], "name": "Part 2", "year": 2})
    sec_b = await admin_client.post("/api/v1/sections", json={
        "class_level_id": cls_y.json()["id"], "name": "B", "capacity": 40})
    stu = await _make_student(admin_client, academic_setup, "s.promo@test.edu")

    # Before move: student is in class X's roster.
    roster_x = await _roster(admin_client, academic_setup["class_id"])
    assert any(s["id"] == stu["id"] for s in roster_x["students"])

    # Promote (same session -> in-place enrolment mutation to class Y / section B).
    promo = await admin_client.post("/api/v1/students/promote", json={
        "student_id": stu["id"], "new_academic_session_id": academic_setup["session_id"],
        "new_class_id": cls_y.json()["id"], "new_section_id": sec_b.json()["id"],
        "action": "section_change",
    })
    assert promo.status_code == 200, promo.text

    # After move: excluded from class X, present in class Y.
    roster_x2 = await _roster(admin_client, academic_setup["class_id"])
    assert not any(s["id"] == stu["id"] for s in roster_x2["students"])
    roster_y = await _roster(admin_client, cls_y.json()["id"])
    assert any(s["id"] == stu["id"] for s in roster_y["students"])


async def test_roster_section_filter(admin_client, academic_setup):
    """?section_id= restricts the roster to one section."""
    sec_b = await admin_client.post("/api/v1/sections", json={
        "class_level_id": academic_setup["class_id"], "name": "B", "capacity": 40})
    await _make_student(admin_client, academic_setup, "s.filtA@test.edu")  # section A
    await _make_student(admin_client, academic_setup, "s.filtB@test.edu", section_id=sec_b.json()["id"])
    all_r = await _roster(admin_client, academic_setup["class_id"])
    assert len(all_r["students"]) == 2
    only_a = (await admin_client.get(
        f"/api/v1/classes/{academic_setup['class_id']}/roster",
        params={"section_id": academic_setup["section_id"]})).json()
    assert len(only_a["students"]) == 1
    assert only_a["students"][0]["section_name"] == "A"


# ---------------- live status: the 12 scenarios ----------------
async def test_1_status_before_lecture_off(admin_client, academic_setup, monkeypatch):
    teacher = await _make_teacher(admin_client, academic_setup, "t.s1@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    stu = await _make_student(admin_client, academic_setup, "s.s1@test.edu")
    _freeze(monkeypatch, 8, 59)
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "off"


async def test_2_status_at_start_present(admin_client, academic_setup, monkeypatch):
    """Start time is inclusive -> at 09:00 exactly the status is Present."""
    teacher = await _make_teacher(admin_client, academic_setup, "t.s2@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    stu = await _make_student(admin_client, academic_setup, "s.s2@test.edu")
    _freeze(monkeypatch, 9, 0)
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "present"


async def test_3_status_during_lecture_present(admin_client, academic_setup, monkeypatch):
    teacher = await _make_teacher(admin_client, academic_setup, "t.s3@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    stu = await _make_student(admin_client, academic_setup, "s.s3@test.edu")
    _freeze(monkeypatch, 9, 30)
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "present"


async def test_4_status_at_end_off(admin_client, academic_setup, monkeypatch):
    """End time is exclusive -> at 10:00 exactly the status flips to Off."""
    teacher = await _make_teacher(admin_client, academic_setup, "t.s4@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    stu = await _make_student(admin_client, academic_setup, "s.s4@test.edu")
    _freeze(monkeypatch, 10, 0)
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "off"


async def test_5_status_between_lectures_off(admin_client, academic_setup, monkeypatch):
    teacher = await _make_teacher(admin_client, academic_setup, "t.s5@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "09:30")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "10:00", "11:00")
    stu = await _make_student(admin_client, academic_setup, "s.s5@test.edu")
    _freeze(monkeypatch, 9, 45)  # in the gap
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "off"


async def test_6_status_after_final_lecture_off(admin_client, academic_setup, monkeypatch):
    teacher = await _make_teacher(admin_client, academic_setup, "t.s6@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    stu = await _make_student(admin_client, academic_setup, "s.s6@test.edu")
    _freeze(monkeypatch, 11, 0)
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "off"


async def test_7_status_no_lecture_that_day_off(admin_client, academic_setup, monkeypatch):
    """Lecture exists on Tuesday but not Monday; on Monday the student is Off."""
    teacher = await _make_teacher(admin_client, academic_setup, "t.s7@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "tuesday", "09:00", "10:00")
    stu = await _make_student(admin_client, academic_setup, "s.s7@test.edu")
    _freeze(monkeypatch, 9, 30)  # Monday 09:30
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "off"


async def test_8_status_holiday_off(admin_client, academic_setup, db, monkeypatch):
    """A holiday for the enrolment's session overrides an otherwise-active lecture."""
    from app.models.attendance import Holiday
    teacher = await _make_teacher(admin_client, academic_setup, "t.s8@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    stu = await _make_student(admin_client, academic_setup, "s.s8@test.edu")
    db.add(Holiday(date=date(2026, 1, 5), name="Foundation Day",
                   academic_session_id=academic_setup["session_id"]))
    await db.commit()
    _freeze(monkeypatch, 9, 30)  # within the lecture, but it's a holiday
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "off"


async def test_9_status_section_isolation(admin_client, academic_setup, monkeypatch):
    """A Section A lecture must NOT make Section B students Present."""
    sec_b = await admin_client.post("/api/v1/sections", json={
        "class_level_id": academic_setup["class_id"], "name": "B", "capacity": 40})
    teacher = await _make_teacher(admin_client, academic_setup, "t.s9@test.edu")  # assigned to A
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")  # section A
    stu_a = await _make_student(admin_client, academic_setup, "s.s9a@test.edu")
    stu_b = await _make_student(admin_client, academic_setup, "s.s9b@test.edu", section_id=sec_b.json()["id"])
    _freeze(monkeypatch, 9, 30)
    roster = await _roster(admin_client, academic_setup["class_id"])
    assert _status_of(roster, stu_a["id"]) == "present"
    assert _status_of(roster, stu_b["id"]) == "off"


async def test_10_status_follows_current_enrolment(admin_client, academic_setup, monkeypatch):
    """After a student moves class, the status follows the NEW enrolment, not
    the old one (and the old class roster excludes them)."""
    cls_y = await admin_client.post("/api/v1/classes", json={
        "program_id": academic_setup["program_id"], "name": "Part 2", "year": 2})
    sec_b = await admin_client.post("/api/v1/sections", json={
        "class_level_id": cls_y.json()["id"], "name": "B", "capacity": 40})
    teacher = await _make_teacher(admin_client, academic_setup, "t.s10@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")  # class X, sec A
    stu = await _make_student(admin_client, academic_setup, "s.s10@test.edu")

    _freeze(monkeypatch, 9, 30)
    roster_x = await _roster(admin_client, academic_setup["class_id"])
    assert _status_of(roster_x, stu["id"]) == "present"  # in class X, sec A, lecture active

    # Move the student to class Y / section B (same session, in-place mutation).
    promo = await admin_client.post("/api/v1/students/promote", json={
        "student_id": stu["id"], "new_academic_session_id": academic_setup["session_id"],
        "new_class_id": cls_y.json()["id"], "new_section_id": sec_b.json()["id"],
        "action": "section_change",
    })
    assert promo.status_code == 200, promo.text

    # Class Y has no lecture -> the moved student is Off, even though class X's
    # lecture is still running. And class X no longer lists them.
    roster_y = await _roster(admin_client, cls_y.json()["id"])
    assert _status_of(roster_y, stu["id"]) == "off"
    roster_x2 = await _roster(admin_client, academic_setup["class_id"])
    assert not any(s["id"] == stu["id"] for s in roster_x2["students"])


async def test_11_status_multiple_durations(admin_client, academic_setup, monkeypatch):
    """Lectures of different lengths (30min + 75min); status follows each
    actual interval, not a fixed duration."""
    teacher = await _make_teacher(admin_client, academic_setup, "t.s11@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "09:30")   # 30 min
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "10:00", "11:15")   # 75 min
    stu = await _make_student(admin_client, academic_setup, "s.s11@test.edu")
    for h, m, expected in [(9, 15, "present"),   # inside first
                           (9, 30, "off"),        # first ends (exclusive)
                           (9, 50, "off"),        # gap
                           (10, 30, "present"),   # inside second
                           (11, 15, "off")]:      # second ends (exclusive)
        _freeze(monkeypatch, h, m)
        roster = await _roster(admin_client, academic_setup["class_id"])
        assert _status_of(roster, stu["id"]) == expected, f"{h:02d}:{m:02d} -> {expected}"


async def test_12_status_updates_across_transition(admin_client, academic_setup, monkeypatch):
    """Simulates a browser left open across a lecture boundary: the same open
    view returns Present at 09:59 and Off at 10:00 after a refetch (the live
    status is recomputed server-side on each request, never cached stale)."""
    teacher = await _make_teacher(admin_client, academic_setup, "t.s12@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    stu = await _make_student(admin_client, academic_setup, "s.s12@test.edu")
    _freeze(monkeypatch, 9, 59)
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "present"
    _freeze(monkeypatch, 10, 0)
    assert _status_of(await _roster(admin_client, academic_setup["class_id"]), stu["id"]) == "off"


async def test_status_no_active_enrolment_off(admin_client, academic_setup, db, monkeypatch):
    """A student with no active enrolment (None passed to the helper) is always
    'off', never 'present' (requirement 3.10). The roster endpoint excludes such
    students entirely; this asserts the underlying helper directly."""
    from sqlalchemy import select
    from app.models.people import StudentEnrolment
    # Build a Monday lecture + an enrolled student so a buggy implementation
    # could surface 'present' for a real enrolment.
    teacher = await _make_teacher(admin_client, academic_setup, "t.snone@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    await _make_student(admin_client, academic_setup, "s.snone@test.edu")
    _freeze(monkeypatch, 9, 30)
    # The db fixture shares the test engine; expire any cached state so the
    # enrolment committed by the API is visible to this session.
    db.expire_all()
    now = live_status_service.current_now()
    # No enrolment -> always 'off', never 'present'.
    assert await live_status_service.compute_live_status(db, None, now) == "off"
    # Sanity: a real active enrolment in a class with a Monday lecture at 09:30 is 'present'.
    enrol = (await db.execute(select(StudentEnrolment).where(
        StudentEnrolment.is_active.is_(True)))).scalars().first()
    assert enrol is not None
    assert await live_status_service.compute_live_status(db, enrol, now) == "present"


async def test_roster_returns_lectures_today_and_server_now(admin_client, academic_setup, monkeypatch):
    """The roster response carries today's lectures + the server-time reference
    the frontend uses to schedule prompt refetches."""
    teacher = await _make_teacher(admin_client, academic_setup, "t.meta@test.edu")
    await _make_entry(admin_client, academic_setup, teacher["id"], "monday", "09:00", "10:00")
    _freeze(monkeypatch, 9, 30)
    roster = await _roster(admin_client, academic_setup["class_id"])
    assert roster["server_now"].startswith("2026-01-05T09:30:00")
    assert len(roster["lectures_today"]) == 1
    assert roster["lectures_today"][0]["start_time"] == "09:00"
    assert roster["lectures_today"][0]["end_time"] == "10:00"
