"""Unit tests: examination marks computation."""
import pytest

from app.services.exam_marks import (
    MarksError,
    MarkInput,
    class_average,
    compute_mark_result,
    validate_mark,
)
from app.services.grading import Boundary

BS = [
    Boundary("F", 0, 40, False), Boundary("C", 40, 50, True),
    Boundary("B", 50, 70, True), Boundary("A", 70, 100, True),
]


def test_present_student_grade():
    r = compute_mark_result(MarkInput("s1", 85, False), max_marks=100, passing_marks=40, boundaries=BS)
    assert r.is_absent is False
    assert r.percentage == 85.0
    assert r.grade == "A"
    assert r.is_pass is True


def test_absent_student_distinct_from_zero():
    r_absent = compute_mark_result(MarkInput("s2", 0, True), max_marks=100, passing_marks=40, boundaries=BS)
    r_zero = compute_mark_result(MarkInput("s3", 0, False), max_marks=100, passing_marks=40, boundaries=BS)
    assert r_absent.is_absent is True and r_absent.is_pass is False
    assert r_zero.is_absent is False and r_zero.is_pass is False  # 0 < 40 -> fail
    assert r_absent.grade is None


def test_validate_mark_rejects_negative():
    with pytest.raises(MarksError):
        validate_mark(-1, 100, False)


def test_validate_mark_rejects_above_max_when_present():
    with pytest.raises(MarksError):
        validate_mark(120, 100, False)
    # absent student with marks > max is allowed (marks zeroed anyway)
    validate_mark(120, 100, True)


def test_class_average_excludes_absent():
    results = [
        compute_mark_result(MarkInput("s1", 80, False), max_marks=100, passing_marks=40, boundaries=BS),
        compute_mark_result(MarkInput("s2", 60, False), max_marks=100, passing_marks=40, boundaries=BS),
        compute_mark_result(MarkInput("s3", 0, True), max_marks=100, passing_marks=40, boundaries=BS),
    ]
    # average of 80 and 60 = 70
    assert class_average(results) == 70.0


def test_class_average_empty():
    assert class_average([]) == 0.0
