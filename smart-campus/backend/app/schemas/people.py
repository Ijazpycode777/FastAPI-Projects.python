"""People schemas: guardians, students, teachers, enrolments, history, board records."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMBase


# ---------------- Guardian ----------------
class GuardianIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    phone: str = Field(min_length=4, max_length=40)
    email: EmailStr | None = None
    relationship_type: str = Field(default="Guardian", max_length=40)
    occupation: str | None = None


class GuardianOut(ORMBase):
    id: str
    name: str
    phone: str
    email: str | None = None
    relationship_type: str
    occupation: str | None = None


# ---------------- Teacher ----------------
class TeacherCreateIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: str | None = None
    employee_id: str = Field(min_length=1, max_length=32)
    department: str | None = None
    designation: str = "Lecturer"
    joining_date: date
    password: str = Field(min_length=10, max_length=128)


class TeacherUpdateIn(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    department: str | None = None
    designation: str | None = None
    employment_status: str | None = None


class TeacherOut(ORMBase):
    id: str
    user_id: str
    employee_id: str
    full_name: str
    email: str
    phone: str | None = None
    department: str | None = None
    designation: str
    joining_date: date
    employment_status: str


# ---------------- Student ----------------
class StudentCreateIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, pattern="^(male|female|other)$")
    admission_date: date
    # Free-text placement: the admin types names (like a username — no fixed
    # dropdown values). The service find-or-creates the underlying
    # program/class/section/session rows so attendance, timetable and marks
    # (which join on the real foreign keys) keep working.
    program: str = Field(min_length=1, max_length=120)
    class_name: str = Field(min_length=1, max_length=60)
    section: str = Field(min_length=1, max_length=16)
    academic_session: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=10, max_length=128)
    guardian: GuardianIn | None = None
    # Optional prior board records captured at admission
    matric_board: str | None = None
    matric_year: int | None = None
    matric_total: int | None = None
    matric_obtained: int | None = None
    matric_grade: str | None = None
    inter_board: str | None = None
    inter_year: int | None = None
    inter_total: int | None = None
    inter_obtained: int | None = None
    inter_grade: str | None = None

    @field_validator("matric_total", "matric_obtained", "inter_total", "inter_obtained")
    @classmethod
    def _non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("marks must be non-negative")
        return v

    @field_validator("matric_obtained", "inter_obtained")
    @classmethod
    def _obtained_le_total(cls, v, info):
        # Cross-field validated in service; here only basic bounds.
        return v


class StudentUpdateIn(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, pattern="^(male|female|other)$")
    account_status: str | None = Field(default=None, pattern="^(active|inactive|graduated|left|suspended)$")
    # Free-text placement (optional). If any of these is set, the service
    # find-or-creates the resolved rows and updates the student's placement.
    program: str | None = Field(default=None, min_length=1, max_length=120)
    class_name: str | None = Field(default=None, min_length=1, max_length=60)
    section: str | None = Field(default=None, min_length=1, max_length=16)
    academic_session: str | None = Field(default=None, min_length=1, max_length=40)


class StudentOut(ORMBase):
    id: str
    user_id: str
    admission_number: str
    full_name: str
    email: str
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    admission_date: date
    account_status: str
    current_program_id: str | None = None
    current_class_id: str | None = None
    current_section_id: str | None = None
    current_session_id: str | None = None
    current_roll_number: int | None = None


class StudentDetailOut(StudentOut):
    guardian: GuardianOut | None = None
    program_name: str | None = None
    class_name: str | None = None
    section_name: str | None = None
    session_name: str | None = None


class BoardRecordIn(BaseModel):
    level: str = Field(pattern="^(matric|inter_part1)$")
    board: str
    examination_year: int = Field(ge=1990, le=2100)
    total_marks: int = Field(ge=1)
    obtained_marks: int = Field(ge=0)
    grade: str | None = None

    @field_validator("obtained_marks")
    @classmethod
    def _obtained_le_total(cls, v, info):
        total = info.data.get("total_marks")
        if total is not None and v > total:
            raise ValueError("obtained_marks cannot exceed total_marks")
        return v


class BoardRecordOut(ORMBase):
    id: str
    student_id: str
    level: str
    board: str
    examination_year: int
    total_marks: int
    obtained_marks: int
    grade: str | None = None
    percentage: float


class EnrolmentOut(ORMBase):
    id: str
    student_id: str
    academic_session_id: str
    program_id: str
    class_id: str
    section_id: str
    roll_number: int
    is_active: bool


class PromoteIn(BaseModel):
    """Promote a student to a new class/section/session."""
    student_id: str
    new_academic_session_id: str
    new_class_id: str
    new_section_id: str
    new_program_id: str | None = None
    action: str = Field(default="promoted", pattern="^(promoted|repeated|section_change)$")
    note: str | None = None
