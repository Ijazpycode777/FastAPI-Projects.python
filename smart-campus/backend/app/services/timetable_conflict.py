"""Timetable conflict detection (pure logic).

A conflict exists when two entries for the same day overlap in time AND share
one of: teacher, or class/section. (Classroom-based booking was removed along
with the classroom feature — see migration 0006.)
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
    class_id: str
    section_id: str | None


def times_overlap(a_start: time, a_end: time, b_start: time, b_end: time) -> bool:
    """Half-open overlap: touching endpoints (a_end == b_start) do NOT conflict."""
    return a_start < b_end and b_start < a_end


def find_conflict(new: EntryRef, existing: list[EntryRef]) -> EntryRef | None:
    """Return the first conflicting entry, or None.

    A conflict exists when two entries share the same day and overlap in time
    AND share a teacher OR share the relevant class/section scope. The
    class/section rule (D5) is:

      * Same teacher is ALWAYS a conflict (a teacher cannot be in two places).
      * Same class + same section (both non-NULL and equal) -> conflict.
      * Same class + either entry is class-wide (section NULL) -> conflict
        (a class-wide lecture occupies every section of the class).
      * Same class + DIFFERENT non-NULL sections -> NOT a conflict: different
        sections of one class may run simultaneous lessons (independent sections).

    This corrects the previous logic which treated same-class as an
    unconditional conflict and thereby blocked legitimate per-section parallel
    lessons and the coexistence of class-wide and section-specific entries.
    """
    for e in existing:
        if e.id == new.id:
            continue
        if e.day_of_week != new.day_of_week:
            continue
        if not times_overlap(new.start_time, new.end_time, e.start_time, e.end_time):
            continue
        # Same teacher cannot be in two places at once.
        if e.teacher_id == new.teacher_id:
            return e
        # Same class scope: conflict only if the entries share a section or one
        # is class-wide (NULL section). Different sections of the same class are
        # allowed to run in parallel.
        if e.class_id == new.class_id:
            same_section = (
                (new.section_id is not None and e.section_id == new.section_id)
                or (new.section_id is None and e.section_id is None)
            )
            classwide_clash = (new.section_id is None) or (e.section_id is None)
            if same_section or classwide_clash:
                return e
    return None


def conflict_reason(conflict: EntryRef, new: EntryRef) -> str:
    if conflict.teacher_id == new.teacher_id:
        return "Teacher is already scheduled at this time."
    if conflict.class_id == new.class_id:
        # A class-wide entry (either side, NULL section) clashes with the whole class.
        if new.section_id is None or conflict.section_id is None:
            return "Class already has a lecture at this time (class-wide entry)."
        return "This section already has a lecture at this time."
    return "Scheduling conflict."
