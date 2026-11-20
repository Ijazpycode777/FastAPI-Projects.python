"""Unit tests: pure grading logic."""
import pytest

from app.services.grading import (
    Boundary,
    GradingError,
    compute_grade,
    is_pass_for,
    next_version,
    percentage_for,
    validate_boundaries,
)


def _std_boundaries():
    return [
        Boundary("F", 0, 40, False),
        Boundary("C", 40, 50, True),
        Boundary("B", 50, 70, True),
        Boundary("A", 70, 85, True),
        Boundary("A+", 85, 100, True),
    ]


def test_validate_boundaries_ok():
    validate_boundaries(_std_boundaries())  # no exception


def test_validate_boundaries_gap_rejected():
    bs = [Boundary("F", 0, 39.99, False), Boundary("C", 40, 100, True)]
    with pytest.raises(GradingError):
        validate_boundaries(bs)


def test_validate_boundaries_overlap_rejected():
    bs = [Boundary("F", 0, 50, False), Boundary("C", 40, 100, True)]
    with pytest.raises(GradingError):
        validate_boundaries(bs)


def test_validate_boundaries_must_start_at_zero():
    bs = [Boundary("C", 10, 100, True)]
    with pytest.raises(GradingError):
        validate_boundaries(bs)


def test_validate_boundaries_must_reach_100():
    bs = [Boundary("F", 0, 60, False)]
    with pytest.raises(GradingError):
        validate_boundaries(bs)


def test_compute_grade_half_open():
    bs = _std_boundaries()
    assert compute_grade(0, bs) == ("F", False)
    assert compute_grade(39.99, bs) == ("F", False)
    assert compute_grade(40, bs) == ("C", True)        # boundary belongs to upper band
    assert compute_grade(69.99, bs) == ("B", True)
    assert compute_grade(70, bs) == ("A", True)
    assert compute_grade(100, bs) == ("A+", True)


def test_compute_grade_clamps():
    bs = _std_boundaries()
    assert compute_grade(-5, bs)[0] == "F"
    assert compute_grade(150, bs)[0] == "A+"


def test_percentage_for():
    assert percentage_for(45, 60) == 75.0
    assert percentage_for(0, 100) == 0.0
    assert percentage_for(100, 0) == 0.0  # guard against div-by-zero


def test_is_pass_for():
    assert is_pass_for(45, 40, 100) is True
    assert is_pass_for(39, 40, 100) is False
    assert is_pass_for(50, 40, 0) is False  # max 0 -> not pass


def test_next_version():
    assert next_version([]) == 1
    assert next_version([1, 2, 5]) == 6
