"""Live, timetable-based student status for the Classes Distribution roster.

The status shown on the roster ("Present" / "Off right now") is a real-time
availability indicator derived from the existing timetable: it answers "is this
student's class/section in a scheduled lecture right now?" It is NOT attendance
-- it never writes to ``AttendanceRecord`` and is independent of the
present/absent/late/excused attendance statuses. Attendance records, marking,
reports and history are untouched.

Time handling
-------------
* ``current_now()`` is the single source of "now" (in the college timezone).
  Tests monkeypatch it to freeze time; the roster endpoint always uses the real
  now, so the same code path runs in production and under test.
* Interval convention: ``start_time`` inclusive, ``end_time`` exclusive -- at
  the exact end time the status flips to "Off right now".
* Section-aware: a lecture for Section A does NOT make Section B students
  Present. A class-wide entry (``section_id IS NULL``) applies to every section,
  preserving the existing class-wide assignment semantics.
* Holiday-aware: a day flagged in the ``holidays`` table for the enrolment's
  academic session is always "Off right now".

The student's CURRENT active enrolment (``StudentEnrolment.is_active=True``) is
the source of truth for class/section/session -- a promoted/transferred
student's old enrolment is ``is_active=False`` and is never consulted, so the
status follows the student's current placement.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.models.academic import Section, Subject
from app.models.attendance import Holiday
from app.models.people import StudentEnrolment
from app.models.timetable import TimetableEntry

LiveStatus = Literal["present", "off"]

# Monday=0 ... Sunday=6, matching TimetableEntry.day_of_week values (the
# lowercase weekday strings enforced by the entry_day_check constraint).
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.college_timezone)


def current_now() -> datetime:
    """The authoritative 'now' in the college timezone.

    Centralised so tests can monkeypatch it (the suite has no freezegun /
    time_machine) and every status computation agrees on the same instant. The
    roster endpoint calls this; tests replace it with a frozen datetime.
    """
    return datetime.now(_tz())


def weekday_name(now: datetime) -> str:
    """Lowercase weekday name matching ``TimetableEntry.day_of_week``."""
    return _WEEKDAYS[now.weekday()]


async def is_holiday(db: AsyncSession, academic_session_id: str, on_date: date) -> bool:
    """True if ``on_date`` is a college holiday for the given academic session."""
    result = await db.execute(
        select(Holiday).where(
            Holiday.academic_session_id == academic_session_id,
            Holiday.date == on_date,
        )
    )
    return result.scalar_one_or_none() is not None


async def _entries_for_day(
    db: AsyncSession, class_id: str, section_id: str | None,
    academic_session_id: str, day: str,
) -> list[TimetableEntry]:
    """Non-cancelled timetable entries for a class/section on ``day``.

    Section-aware: an entry applies to a student's section if its
    ``section_id`` matches the student's section OR is NULL (class-wide),
    matching ``timetable_service.weekly_for_class``.
    """
    stmt = select(TimetableEntry).where(
        TimetableEntry.class_id == class_id,
        TimetableEntry.academic_session_id == academic_session_id,
        TimetableEntry.day_of_week == day,
        TimetableEntry.is_cancelled.is_(False),
    )
    if section_id is not None:
        stmt = stmt.where(
            (TimetableEntry.section_id == section_id) | (TimetableEntry.section_id.is_(None))
        )
    return list((await db.execute(stmt)).scalars().all())


async def compute_live_status(
    db: AsyncSession, enrolment: StudentEnrolment | None, now: datetime,
) -> LiveStatus:
    """``"present"`` if the student's class/section is in a scheduled lecture at
    ``now``, otherwise ``"off"``.

    A student with no active enrolment is always ``"off"`` (requirement 3.10).
    Holidays and days with no scheduled lectures are ``"off"``. The interval is
    ``[start_time, end_time)``: inclusive of the start, exclusive of the end, so
    at the exact end time the status is ``"off"`` (requirement 3.6).
    """
    if enrolment is None:
        return "off"
    local = now.astimezone(_tz())
    if await is_holiday(db, enrolment.academic_session_id, local.date()):
        return "off"
    day = weekday_name(local)
    entries = await _entries_for_day(
        db, enrolment.class_id, enrolment.section_id,
        enrolment.academic_session_id, day,
    )
    now_time = local.time()
    for e in entries:
        if e.start_time <= now_time < e.end_time:
            return "present"
    return "off"


async def lectures_for_class_today(
    db: AsyncSession, class_id: str, academic_session_id: str, now: datetime,
) -> list[dict]:
    """Today's non-cancelled lectures for the class (all sections) as plain
    dicts for the API response.

    Returned alongside the roster so the frontend can schedule a refetch at the
    next lecture start/end boundary (prompt transitions) without polling every
    second. ``section_id``/``section_name`` are included so a per-section view is
    possible; ``subject_name`` makes the optional "today's lectures" list readable.
    """
    day = weekday_name(now.astimezone(_tz()))
    stmt = (
        select(TimetableEntry, Section, Subject)
        .outerjoin(Section, TimetableEntry.section_id == Section.id)
        .join(Subject, TimetableEntry.subject_id == Subject.id)
        .where(
            TimetableEntry.class_id == class_id,
            TimetableEntry.academic_session_id == academic_session_id,
            TimetableEntry.day_of_week == day,
            TimetableEntry.is_cancelled.is_(False),
        )
        .order_by(TimetableEntry.start_time)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            # "HH:MM" (not isoformat's "HH:MM:SS") so the frontend can compose
            # `${day}T${start_time}:00${offset}` cleanly for transition scheduling.
            "start_time": e.start_time.strftime("%H:%M"),
            "end_time": e.end_time.strftime("%H:%M"),
            "section_id": str(e.section_id) if e.section_id else None,
            "section_name": s.name if s is not None else None,
            "subject_name": subj.name if subj is not None else None,
        }
        for e, s, subj in rows
    ]
