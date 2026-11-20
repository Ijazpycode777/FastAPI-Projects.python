"""Timetable conflict detection (pure logic).

A conflict exists when two entries for the same day overlap in time AND share
one of: teacher, classroom, or class/section.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time


@dataclass
class EntryRef:
    id: str
    day_of_week: str
    start_time: time
    end_time: time
    teacher_id: str
    classroom_id: str | None
    class_id: str
    section_id: str | None


def times_overlap(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    """Half-open overlap: touching endpoints (a_end == b_start) do NOT conflict."""
    return a_start < b_end and b_start < a_end


def find_conflict(new: EntryRef, existing: list[EntryRef]) -> EntryRef | None:
    """Return the first conflicting entry, or None.

    Checks (same day + overlapping time) AND shared teacher/classroom/class/section.
    """
    for e in existing:
        if e.id == new.id:
            continue
        if e.day_of_week != new.day_of_week:
            continue
        if not times_overlap(new.start_time, new.end_time, e.start_time, e.end_time):
            continue
        if e.teacher_id == new.teacher_id:
            return e
        if new.classroom_id and e.classroom_id == new.classroom_id:
            return e
        if e.class_id == new.class_id:
            # Same class is always a conflict; section optional refinement.
            return e
        if new.section_id and e.section_id == new.section_id:
            return e
    return None


def conflict_reason(conflict: EntryRef, new: EntryRef) -> str:
    if conflict.teacher_id == new.teacher_id:
        return "Teacher is already scheduled at this time."
    if new.classroom_id and conflict.classroom_id == new.classroom_id:
        return "Classroom is already booked at this time."
    if conflict.class_id == new.class_id:
        return "Class already has a lecture at this time."
    if new.section_id and conflict.section_id == new.section_id:
        return "Section already has a lecture at this time."
    return "Scheduling conflict."
