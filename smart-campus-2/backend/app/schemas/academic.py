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


class ClassroomIn(BaseModel):
    room_number: str = Field(min_length=1, max_length=24)
    building: str | None = None
    capacity: int = Field(default=40, ge=1, le=1000)
    is_active: bool = True


class ClassroomOut(ORMBase):
    id: str
    room_number: str
    building: str | None = None
    capacity: int
    is_active: bool
