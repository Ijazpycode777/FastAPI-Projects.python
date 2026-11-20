"""Teacher self-attendance logic (pure).

Server-generated timestamps. Worked minutes = checkout - checkin.
Late if check_in > work_start + threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta


@dataclass
class CheckResult:
    status: str           # present | late | absent
    work_minutes: int
    is_active: bool       # True if check-in has no matching checkout


def parse_work_start(value: str) -> time:
    """Parse 'HH:MM' into a time object."""
    h, m = value.split(":")
    return time(int(h), int(m))


def compute_late_status(
    check_in: datetime,
    work_start: time,
    late_threshold_minutes: int,
) -> str:
    """Return 'late' if check_in is later than work_start + threshold, else 'present'."""
    ws = datetime.combine(check_in.date(), work_start, tzinfo=check_in.tzinfo)
    if check_in > ws + timedelta(minutes=late_threshold_minutes):
        return "late"
    return "present"


def compute_work_minutes(check_in: datetime, check_out: datetime) -> int:
    """Worked minutes between check-in and check-out.

    Coerces naive datetimes to UTC so mixed-awareness values (which can occur
    when a tz-aware timestamp is stored in and read back from a tz-naive
    column) do not raise.
    """
    from datetime import timezone

    def _aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    delta = _aware(check_out) - _aware(check_in)
    if delta.total_seconds() < 0:
        return 0
    return int(delta.total_seconds() // 60)


def finalize_status(check_in: datetime | None, check_out: datetime | None) -> str:
    """Status from a completed (or in-progress) record. 'absent' if never checked in."""
    if check_in is None:
        return "absent"
    if check_out is None:
        return "present"  # active check-in, considered present until checkout
    return "present"


def can_check_out(record_check_in: datetime | None, record_check_out: datetime | None) -> bool:
    """Allow checkout only if there's an active check-in and no checkout yet."""
    return record_check_in is not None and record_check_out is None


def can_check_in(record_check_in: datetime | None) -> bool:
    """Allow check-in only if there isn't an active one for the day."""
    return record_check_in is None
