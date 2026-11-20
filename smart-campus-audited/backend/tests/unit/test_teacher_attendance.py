"""Unit tests: teacher self-attendance logic."""
from datetime import datetime, time, timezone

from app.services.teacher_attendance_logic import (
    can_check_in,
    can_check_out,
    compute_late_status,
    compute_work_minutes,
    finalize_status,
    parse_work_start,
)


def test_parse_work_start():
    assert parse_work_start("08:30") == time(8, 30)
    assert parse_work_start("17:00") == time(17, 0)


def test_late_when_after_threshold():
    ws = parse_work_start("08:30")
    check_in = datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc)  # 30 min late
    assert compute_late_status(check_in, ws, 15) == "late"


def test_present_when_within_threshold():
    ws = parse_work_start("08:30")
    check_in = datetime(2026, 1, 1, 8, 40, tzinfo=timezone.utc)  # 10 min late
    assert compute_late_status(check_in, ws, 15) == "present"


def test_present_exactly_at_start():
    ws = parse_work_start("08:30")
    check_in = datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc)
    assert compute_late_status(check_in, ws, 15) == "present"


def test_compute_work_minutes():
    ci = datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc)
    co = datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc)
    assert compute_work_minutes(ci, co) == 480


def test_compute_work_minutes_zero_when_negative():
    ci = datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc)
    co = datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc)
    assert compute_work_minutes(ci, co) == 0


def test_can_check_in_only_when_none():
    assert can_check_in(None) is True
    assert can_check_in(datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc)) is False


def test_can_check_out_requires_active_checkin():
    ci = datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc)
    assert can_check_out(None, None) is False
    assert can_check_out(ci, None) is True
    assert can_check_out(ci, datetime(2026, 1, 1, 16, 30, tzinfo=timezone.utc)) is False


def test_finalize_status():
    assert finalize_status(None, None) == "absent"
    assert finalize_status(datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc), None) == "present"
