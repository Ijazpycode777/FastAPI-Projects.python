"""Academic structure schemas."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMBase


class AcademicSessionIn(BaseModel):
    name: str = Field(min_length=3, max_length=40)
    start_date: date
    end_date: date
    is_active: bool = False

    @field_validator("end_date")
    @classmethod
    def _end_after_start(cls, v, info):
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("end_date must be after start_date")
        return v


class AcademicSessionOut(ORMBase):
    id: str
    name: str
    start_date: date
    end_date: date
    is_active: bool


class ProgramIn(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class ProgramOut(ORMBase):
    id: str
    code: str
    name: str
    description: str | None = None


class ClassLevelIn(BaseModel):
    program_id: str
    name: str = Field(min_length=1, max_length=60)
    year: int = Field(ge=1, le=6)


class ClassLevelOut(ORMBase):
    id: str
    program_id: str
    name: str
    year: int


class SectionIn(BaseModel):
    class_level_id: str
    name: str = Field(min_length=1, max_length=16)
    capacity: int = Field(default=40, ge=1, le=500)


class SectionOut(ORMBase):
    id: str
    class_level_id: str
    name: str
    capacity: int


class SubjectIn(BaseModel):
    program_id: str
    code: str = Field(min_length=1, max_length=24)
    name: str = Field(min_length=1, max_length=120)
    theory_marks: int = Field(default=100, ge=0, le=1000)
    practical_marks: int = Field(default=0, ge=0, le=1000)


class SubjectOut(ORMBase):
    id: str
    program_id: str
    code: str
    name: str
    theory_marks: int
    practical_marks: int


class DepartmentOut(ORMBase):
    """Read-only department record. The five fixed rows are migration-seeded;
    there is no create/update/delete schema by design."""
    id: str
    name: str


class AssignmentIn(BaseModel):
    """Validate the teacher-assignment payload (was a raw ``dict`` that raised a
    generic 500 + dev message leak on missing keys)."""
    teacher_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    class_id: str = Field(min_length=1)
    section_id: str | None = None
    academic_session_id: str = Field(min_length=1)


# ---------------- Updates (rename / resize) ----------------
class ProgramUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=16)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None


class ClassLevelUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    year: int | None = Field(default=None, ge=1, le=6)


class SectionUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=16)
    capacity: int | None = Field(default=None, ge=1, le=500)


class SubjectUpdateIn(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=24)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    theory_marks: int | None = Field(default=None, ge=0, le=1000)
    practical_marks: int | None = Field(default=None, ge=0, le=1000)


# ---------------- Classes Distribution (admin management view) ----------------
class SubjectBrief(BaseModel):
    id: str
    code: str
    name: str


class SectionBrief(BaseModel):
    id: str
    name: str
    capacity: int
    enrolled: int


class ClassDistributionOut(BaseModel):
    """A class with its program, sections, designated subjects (the program's
    subjects) and current enrolment counts. Powers the Classes Distribution page."""
    id: str
    program_id: str
    program_name: str
    program_code: str
    name: str
    year: int
    enrolled: int
    sections: list[SectionBrief]
    subjects: list[SubjectBrief]


# ---------------- Classes Distribution roster (live status) ----------------
class ClassRosterStudentOut(BaseModel):
    """One currently-enrolled student on a class roster, with the live
    timetable-based status indicator. ``live_status`` is "present" when the
    student's class/section is in a scheduled lecture right now, else "off". It
    is NOT attendance and never reflects attendance records."""
    id: str
    full_name: str
    admission_number: str
    roll_number: int
    section_name: str | None = None
    session_name: str | None = None
    live_status: str  # "present" | "off"


class ClassRosterLectureOut(BaseModel):
    """A lecture scheduled for the class today (all sections). Returned so the
    frontend can schedule a refetch at the next start/end boundary."""
    start_time: str  # "HH:MM"
    end_time: str
    section_id: str | None = None
    section_name: str | None = None
    subject_name: str | None = None


class ClassRosterOut(BaseModel):
    """The full roster view for a class: currently-enrolled students with live
    status, today's lectures, and the server time reference used to compute
    status (so the client can stay in sync without trusting its own clock)."""
    class_id: str
    class_name: str
    program_name: str | None = None
    year: int
    students: list[ClassRosterStudentOut]
    lectures_today: list[ClassRosterLectureOut]
    server_now: str  # ISO 8601, college timezone, seconds precision
    timezone: str
