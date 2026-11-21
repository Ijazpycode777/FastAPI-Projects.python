"""Campus shifts and roll-number schemes.

A campus shift (Morning / Evening) is a foundational academic structure.
Roll numbers are unique *within a shift*: the same roll number may be reused
across different shifts. Per-class roll-number schemes (prefix + range) are
administrator-configurable and validated on student create/update/promote.
"""
from __future__ import annotations

from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK


class CampusShift(UUIDPK, TimestampMixin, Base):
    """A campus shift, e.g. Morning or Evening."""
    __tablename__ = "campus_shifts"
    __table_args__ = (
        UniqueConstraint("code", name="uq_campus_shift_code"),
        Index("ix_campus_shift_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(40), nullable=False)
    code: Mapped[str] = mapped_column(String(16), nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    students = relationship("Student", back_populates="campus_shift")


class RollNumberScheme(UUIDPK, TimestampMixin, Base):
    """Configurable per-class roll-number prefix + range, per shift.

    A scheme with ``section_id IS NULL`` applies to every section of the class;
    a section-specific scheme takes precedence. Schemes are optional — when none
    exists for a (shift, class[, section]) only uniqueness is enforced.
    """
    __tablename__ = "roll_number_schemes"
    __table_args__ = (
        UniqueConstraint("campus_shift_id", "class_id", "section_id", name="uq_roll_scheme_shift_class_section"),
        CheckConstraint("max_roll >= min_roll", name="roll_scheme_range_check"),
        Index("ix_roll_scheme_class", "class_id"),
    )

    campus_shift_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("campus_shifts.id", ondelete="CASCADE"), nullable=False
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="CASCADE"), nullable=False
    )
    section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="CASCADE"), nullable=True
    )
    prefix: Mapped[str | None] = mapped_column(String(16), nullable=True)
    min_roll: Mapped[int] = mapped_column(Integer, nullable=False)
    max_roll: Mapped[int] = mapped_column(Integer, nullable=False)
    padding: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
