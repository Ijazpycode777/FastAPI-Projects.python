"""Examination & grading schemas."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMBase


# ---------------- Grading policy ----------------
class GradingBoundaryIn(BaseModel):
    grade_name: str = Field(min_length=1, max_length=8)
    min_percentage: float = Field(ge=0, le=100)
    max_percentage: float = Field(ge=0, le=100)
    is_pass: bool = True
    description: str | None = None

    @model_validator(mode="after")
    def _order(self):
        if self.max_percentage < self.min_percentage:
            raise ValueError("max_percentage must be >= min_percentage")
        return self


class GradingPolicyIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str | None = None
    boundaries: list[GradingBoundaryIn] = Field(min_length=1)


class GradingBoundaryOut(ORMBase):
    id: str
    policy_id: str
    grade_name: str
    min_percentage: float
    max_percentage: float
    is_pass: bool
    description: str | None = None


class GradingPolicyOut(ORMBase):
    id: str
    name: str
    version: int
    is_active: bool
    description: str | None = None
    boundaries: list[GradingBoundaryOut] = []


# ---------------- Examination ----------------
class ExaminationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    exam_type: str = Field(pattern="^(monthly_test|class_test|midterm|final|quiz)$")
    academic_session_id: str
    program_id: str
    class_id: str
    section_id: str | None = None
    subject_id: str
    max_marks: int = Field(ge=1, le=1000)
    passing_marks: int = Field(ge=0, le=1000)
    exam_date: date
    grading_policy_id: str | None = None

    @model_validator(mode="after")
    def _passing(self):
        if self.passing_marks > self.max_marks:
            raise ValueError("passing_marks cannot exceed max_marks")
        return self


class ExaminationOut(ORMBase):
    id: str
    name: str
    exam_type: str
    academic_session_id: str
    program_id: str
    class_id: str
    section_id: str | None = None
    subject_id: str
    max_marks: int
    passing_marks: int
    exam_date: date
    status: str
    grading_policy_id: str | None = None
    created_by: str | None = None
    finalized_at: str | None = None


# ---------------- Marks ----------------
class MarkEntryIn(BaseModel):
    student_id: str
    marks_obtained: float = Field(ge=0)
    is_absent: bool = False
    note: str | None = None


class MarkBulkIn(BaseModel):
    entries: list[MarkEntryIn] = Field(min_length=1)


class MarkUpdateIn(BaseModel):
    marks_obtained: float = Field(ge=0)
    is_absent: bool = False
    note: str | None = None


class StudentMarkOut(ORMBase):
    id: str
    examination_id: str
    student_id: str
    subject_id: str
    marks_obtained: float
    is_absent: bool
    grade: str | None = None
    percentage: float | None = None
    is_pass: bool | None = None
    status: str
    recorded_by: str | None = None
    recorded_at: str | None = None


class GradeResult(BaseModel):
    grade: str | None
    percentage: float
    is_pass: bool
