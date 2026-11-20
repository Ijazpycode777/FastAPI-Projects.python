"""Attendance schemas (student + teacher self-attendance)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase

ATTENDANCE_STATUSES = ("present", "absent", "late", "excused")


class AttendanceMarkIn(BaseModel):
    student_id: str
    status: str = Field(pattern="^(present|absent|late|excused)$")


class AttendanceBulkIn(BaseModel):
    timetable_entry_id: str
    attendance_date: date
    marks: list[AttendanceMarkIn] = Field(min_length=1)
    note: str | None = None


class AttendanceUpdateIn(BaseModel):
    status: str = Field(pattern="^(present|absent|late|excused)$")
    note: str | None = None


class AttendanceOut(ORMBase):
    id: str
    student_id: str
    timetable_entry_id: str
    subject_id: str
    teacher_id: str
    class_id: str
    section_id: str | None = None
    academic_session_id: str
    attendance_date: date
    status: str
    marked_by: str | None = None
    marked_at: datetime
    is_finalized: bool
    note: str | None = None


class AttendanceSummary(BaseModel):
    student_id: str
    present: int
    absent: int
    late: int
    excused: int
    total_eligible: int   # present + late + absent
    percentage: float     # (present + late) / total_eligible * 100


# ---------------- Teacher self-attendance ----------------
class TeacherAttendanceOut(ORMBase):
    id: str
    teacher_id: str
    attendance_date: date
    check_in_at: datetime | None = None
    check_out_at: datetime | None = None
    status: str
    work_minutes: int
    note: str | None = None


class TeacherAttendanceSummary(BaseModel):
    teacher_id: str
    days_present: int
    days_late: int
    days_absent: int
    total_working_minutes: int
    late_arrivals: int
