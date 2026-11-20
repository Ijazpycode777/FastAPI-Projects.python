"""Examination marks validation & result calculation (pure logic)."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.grading import Boundary, compute_grade, is_pass_for, percentage_for


class MarksError(Exception):
    pass


@dataclass
class MarkInput:
    student_id: str
    marks_obtained: float
    is_absent: bool = False


@dataclass
class MarkResult:
    student_id: str
    marks_obtained: float
    is_absent: bool
    percentage: float
    grade: str | None
    is_pass: bool


def validate_mark(marks_obtained: float, max_marks: float, is_absent: bool) -> None:
    if marks_obtained < 0:
        raise MarksError("Marks cannot be negative.")
    if not is_absent and marks_obtained > max_marks:
        raise MarksError(f"Marks cannot exceed maximum ({max_marks}).")


def compute_mark_result(
    entry: MarkInput,
    *,
    max_marks: float,
    passing_marks: float,
    boundaries: list[Boundary],
) -> MarkResult:
    """Compute percentage, grade, pass/fail for one mark entry.

    Absent students: percentage 0, grade None, is_pass False (and distinct
    from a present student who scored 0).
    """
    validate_mark(entry.marks_obtained, max_marks, entry.is_absent)
    if entry.is_absent:
        return MarkResult(
            student_id=entry.student_id,
            marks_obtained=0.0,
            is_absent=True,
            percentage=0.0,
            grade=None,
            is_pass=False,
        )
    pct = percentage_for(entry.marks_obtained, max_marks)
    grade, _ = compute_grade(pct, boundaries)
    passed = is_pass_for(entry.marks_obtained, passing_marks, max_marks)
    return MarkResult(
        student_id=entry.student_id,
        marks_obtained=entry.marks_obtained,
        is_absent=False,
        percentage=pct,
        grade=grade,
        is_pass=passed,
    )


def class_average(results: list[MarkResult]) -> float:
    """Average percentage of present students only (absent excluded)."""
    present = [r for r in results if not r.is_absent]
    if not present:
        return 0.0
    return round(sum(r.percentage for r in present) / len(present), 2)
