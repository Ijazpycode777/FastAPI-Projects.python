"""Attendance schemas (student + teacher self-attendance + leave)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

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


class AttendanceBreakdown(BaseModel):
    """Present / Absent / Leave donut data (Part 8 of the spec).

    present = attendance records with status present or late
    absent  = attendance records with status absent
    leave   = scheduled sessions within an approved leave period that have no
              present/absent record
    total_scheduled = present + absent + leave
    percentage = present / total_scheduled * 100

    Legacy ``excused`` records are preserved in the raw attendance history but
    are not collapsed into any of these three segments.
    """
    student_id: str
    present: int
    absent: int
    leave: int
    total_scheduled: int
    percentage: float


# ---------------- Leave records (students + teachers) ----------------
class LeaveIn(BaseModel):
    person_type: str = Field(pattern="^(student|teacher)$")
    student_id: str | None = None
    teacher_id: str | None = None
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def _check_target(self):
        if self.person_type == "student" and not self.student_id:
            raise ValueError("student_id is required for student leave.")
        if self.person_type == "teacher" and not self.teacher_id:
            raise ValueError("teacher_id is required for teacher leave.")
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date.")
        return self


class LeaveOut(ORMBase):
    id: str
    person_type: str
    student_id: str | None = None
    teacher_id: str | None = None
    start_date: date
    end_date: date
    reason: str
    status: str
    approved_by: str | None = None
    created_at: datetime


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
