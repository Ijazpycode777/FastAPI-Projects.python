"""Unit tests: timetable conflict detection."""
from datetime import time

from app.services.timetable_conflict import (
    EntryRef,
    conflict_reason,
    find_conflict,
    times_overlap,
)


def _e(id_, start, end, teacher="t1", room="r1", cls="c1", section="s1"):
    return EntryRef(id_, "monday", time(*start), time(*end), teacher, room, cls, section)


def test_overlap_true():
    assert times_overlap(time(8, 30), time(9, 30), time(9, 0), time(10, 0))


def test_touching_no_overlap():
    assert not times_overlap(time(8, 30), time(9, 30), time(9, 30), time(10, 30))


def test_teacher_conflict_detected():
    e1 = _e("1", (8, 30), (9, 30))
    new = _e("2", (9, 0), (10, 0), teacher="t1", room="r9", cls="c9", section="s9")
    assert find_conflict(new, [e1]) is e1
    assert "Teacher" in conflict_reason(e1, new)


def test_classroom_conflict_detected():
    e1 = _e("1", (8, 30), (9, 30), teacher="tA", room="r1", cls="cA", section="sA")
    new = _e("2", (9, 0), (10, 0), teacher="tB", room="r1", cls="cB", section="sB")
    assert find_conflict(new, [e1]) is e1
    assert "Classroom" in conflict_reason(e1, new)


def test_class_conflict_detected():
    e1 = _e("1", (8, 30), (9, 30), teacher="tA", room="r1", cls="c1", section="sA")
    new = _e("2", (9, 0), (10, 0), teacher="tB", room="r2", cls="c1", section="sB")
    assert find_conflict(new, [e1]) is e1


def test_section_conflict_detected():
    e1 = _e("1", (8, 30), (9, 30), teacher="tA", room="r1", cls="c1", section="s1")
    new = _e("2", (9, 0), (10, 0), teacher="tB", room="r2", cls="c9", section="s1")
    assert find_conflict(new, [e1]) is e1


def test_no_conflict_when_different_day():
    e1 = _e("1", (8, 30), (9, 30))
    new = EntryRef("2", "tuesday", time(9, 0), time(10, 0), "t1", "r1", "c1", "s1")
    assert find_conflict(new, [e1]) is None


def test_no_conflict_when_no_overlap():
    e1 = _e("1", (8, 30), (9, 30))
    new = _e("2", (10, 0), (11, 0))
    assert find_conflict(new, [e1]) is None


def test_self_not_conflict():
    e1 = _e("1", (8, 30), (9, 30))
    assert find_conflict(e1, [e1]) is None
