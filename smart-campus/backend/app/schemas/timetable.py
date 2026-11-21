"""Timetable schemas."""
from __future__ import annotations

from datetime import time

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMBase


class TimetablePeriodIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    day_of_week: str = Field(pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$")
    start_time: time
    end_time: time
    academic_session_id: str

    @model_validator(mode="after")
    def _order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class TimetablePeriodOut(ORMBase):
    id: str
    name: str
    day_of_week: str
    start_time: time
    end_time: time
    academic_session_id: str


class TimetableEntryIn(BaseModel):
    academic_session_id: str
    day_of_week: str = Field(pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$")
    start_time: time
    end_time: time
    subject_id: str
    teacher_id: str
    class_id: str
    section_id: str | None = None
    classroom_id: str | None = None
    period_name: str | None = None

    @model_validator(mode="after")
    def _order(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class TimetableEntryOut(ORMBase):
    id: str
    academic_session_id: str
    day_of_week: str
    start_time: time
    end_time: time
    subject_id: str
    teacher_id: str
    class_id: str
    section_id: str | None = None
    classroom_id: str | None = None
    period_name: str | None = None
    is_cancelled: bool


class TimetableEntryUpdateIn(BaseModel):
    day_of_week: str | None = Field(default=None, pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$")
    start_time: time | None = None
    end_time: time | None = None
    subject_id: str | None = None
    teacher_id: str | None = None
    class_id: str | None = None
    section_id: str | None = None
    classroom_id: str | None = None
    period_name: str | None = None


class TimetableEntryDetailOut(TimetableEntryOut):
    subject_name: str | None = None
    teacher_name: str | None = None
    classroom_number: str | None = None
