"""Campus shift + roll-number scheme schemas."""
from __future__ import annotations

from datetime import time

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMBase


class CampusShiftIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    code: str = Field(min_length=1, max_length=16)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool = True

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        # Tolerate empty-string times from clients (treat as "not set") so a
        # shift can be created without picking times.
        if v in ("", None):
            return None
        return v

    @model_validator(mode="after")
    def _times_ordered(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class CampusShiftOut(ORMBase):
    id: str
    name: str
    code: str
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool


class RollNumberSchemeIn(BaseModel):
    campus_shift_id: str
    class_id: str
    section_id: str | None = None
    prefix: str | None = Field(default=None, max_length=16)
    min_roll: int = Field(ge=0)
    max_roll: int = Field(ge=1)
    padding: int = Field(default=2, ge=1, le=6)

    @model_validator(mode="after")
    def _range(self):
        if self.max_roll < self.min_roll:
            raise ValueError("max_roll must be >= min_roll")
        return self


class RollNumberSchemeOut(ORMBase):
    id: str
    campus_shift_id: str
    class_id: str
    section_id: str | None = None
    prefix: str | None = None
    min_roll: int
    max_roll: int
    padding: int


class CampusShiftUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    code: str | None = Field(default=None, min_length=1, max_length=16)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None


class RollNumberSchemeUpdateIn(BaseModel):
    section_id: str | None = None
    prefix: str | None = Field(default=None, max_length=16)
    min_roll: int | None = Field(default=None, ge=0)
    max_roll: int | None = Field(default=None, ge=1)
    padding: int | None = Field(default=None, ge=1, le=6)

    @model_validator(mode="after")
    def _range(self):
        if self.min_roll is not None and self.max_roll is not None and self.max_roll < self.min_roll:
            raise ValueError("max_roll must be >= min_roll")
        return self
