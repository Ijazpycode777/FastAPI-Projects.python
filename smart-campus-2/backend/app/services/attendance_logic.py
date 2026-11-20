"""Attendance calculation rules (pure logic).

percentage = (present + late) / (present + late + absent) * 100
excused is excluded from the denominator.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

PRESENT = "present"
ABSENT = "absent"
LATE = "late"
EXCUSED = "excused"

ATTENDED = {PRESENT, LATE}
ELIGIBLE = {PRESENT, LATE, ABSENT}  # excused excluded from denominator


@dataclass
class AttendanceCounts:
    present: int = 0
    absent: int = 0
    late: int = 0
    excused: int = 0

    @property
    def total_eligible(self) -> int:
        return self.present + self.late + self.absent

    @property
    def attended(self) -> int:
        return self.present + self.late


def count_statuses(statuses: Iterable[str]) -> AttendanceCounts:
    c = AttendanceCounts()
    for s in statuses:
        if s == PRESENT:
            c.present += 1
        elif s == ABSENT:
            c.absent += 1
        elif s == LATE:
            c.late += 1
        elif s == EXCUSED:
            c.excused += 1
    return c


def attendance_percentage(statuses: Iterable[str]) -> float:
    """Percentage based on the rule above. Returns 0.0 when no eligible records."""
    c = count_statuses(statuses)
    if c.total_eligible == 0:
        return 0.0
    return round((c.attended / c.total_eligible) * 100, 2)


def is_valid_status(status: str) -> bool:
    return status in (PRESENT, ABSENT, LATE, EXCUSED)


def is_attended(status: str) -> bool:
    return status in ATTENDED
