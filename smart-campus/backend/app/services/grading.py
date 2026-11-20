"""Grading policy calculation & boundary validation (pure logic).

Pure functions operate on plain boundaries so unit tests need no database.
The DB-backed ``GradingService`` composes these with queries.
"""
from __future__ import annotations

from dataclasses import dataclass


class GradingError(Exception):
    pass


@dataclass(frozen=True)
class Boundary:
    grade_name: str
    min_percentage: float
    max_percentage: float
    is_pass: bool
    description: str | None = None


def validate_boundaries(boundaries: list[Boundary]) -> None:
    """Ensure boundaries are well-formed, non-overlapping and cover [0, 100].

    Rules:
      * each boundary: 0 <= min <= max <= 100, max >= min
      * no two boundaries overlap
      * the union must cover the full 0..100 range (a grade exists for every %)
    Raises GradingError on any violation.
    """
    if not boundaries:
        raise GradingError("At least one grade boundary is required.")

    for b in boundaries:
        if not (0 <= b.min_percentage <= 100):
            raise GradingError(f"Boundary {b.grade_name}: min_percentage out of range.")
        if not (0 <= b.max_percentage <= 100):
            raise GradingError(f"Boundary {b.grade_name}: max_percentage out of range.")
        if b.max_percentage < b.min_percentage:
            raise GradingError(f"Boundary {b.grade_name}: max < min.")

    sorted_b = sorted(boundaries, key=lambda x: x.min_percentage)
    if sorted_b[0].min_percentage > 0:
        raise GradingError("Boundaries must start at 0%.")
    if sorted_b[-1].max_percentage < 100:
        raise GradingError("Boundaries must cover up to 100%.")

    for prev, cur in zip(sorted_b, sorted_b[1:]):
        # Adjacent boundaries must be contiguous (prev.max == cur.min) and not overlap.
        if cur.min_percentage < prev.max_percentage:
            raise GradingError(
                f"Overlapping boundaries: {prev.grade_name} and {cur.grade_name}."
            )
        if cur.min_percentage > prev.max_percentage:
            raise GradingError(
                f"Gap between {prev.grade_name} (max {prev.max_percentage}) and "
                f"{cur.grade_name} (min {cur.min_percentage})."
            )


def compute_grade(percentage: float, boundaries: list[Boundary]) -> tuple[str | None, bool]:
    """Return (grade_name, is_pass) for a percentage.

    Boundaries are treated as half-open intervals ``[min, max)`` so that
    contiguous boundaries (e.g. F:0-40, C:40-50) are unambiguous: a score of
    exactly 40 falls into C, not F. The boundary whose ``max_percentage`` is
    100 is inclusive on its upper end.
    """
    if percentage < 0:
        percentage = 0.0
    if percentage > 100:
        percentage = 100.0
    for b in boundaries:
        if b.max_percentage >= 100:
            if b.min_percentage <= percentage <= b.max_percentage:
                return b.grade_name, b.is_pass
        elif b.min_percentage <= percentage < b.max_percentage:
            return b.grade_name, b.is_pass
    return None, False


def percentage_for(marks_obtained: float, max_marks: float) -> float:
    """Percentage rounded to 2 decimals. 0 if max_marks <= 0."""
    if max_marks <= 0:
        return 0.0
    return round((marks_obtained / max_marks) * 100, 2)


def is_pass_for(marks_obtained: float, passing_marks: float, max_marks: float) -> bool:
    """Pass if marks_obtained >= passing_marks. Independent of grade boundaries."""
    if max_marks <= 0:
        return False
    return marks_obtained >= passing_marks


def next_version(existing_versions: list[int]) -> int:
    """Next policy version number = max(existing) + 1, or 1 if none."""
    return (max(existing_versions) + 1) if existing_versions else 1
