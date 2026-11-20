"""Unit tests: attendance percentage rule."""
from app.services.attendance_logic import (
    ATTENDED,
    attendance_percentage,
    count_statuses,
    is_attended,
    is_valid_status,
)


def test_percentage_basic():
    # present=2 late=1 absent=1 -> (2+1)/(2+1+1) = 75
    assert attendance_percentage(["present", "present", "late", "absent"]) == 75.0


def test_percentage_excused_excluded_from_denominator():
    # excused does not change the percentage
    assert attendance_percentage(["present", "excused", "excused"]) == 100.0
    assert attendance_percentage(["absent", "excused"]) == 0.0


def test_percentage_no_records():
    assert attendance_percentage([]) == 0.0


def test_percentage_all_late_counts_as_attended():
    assert attendance_percentage(["late", "late", "late"]) == 100.0


def test_counts():
    c = count_statuses(["present", "present", "absent", "late", "excused"])
    assert (c.present, c.late, c.absent, c.excused) == (2, 1, 1, 1)
    assert c.total_eligible == 4
    assert c.attended == 3


def test_status_helpers():
    assert is_valid_status("present")
    assert not is_valid_status("sick")
    assert is_attended("present") and is_attended("late")
    assert not is_attended("absent")
    assert ATTENDED == {"present", "late"}
