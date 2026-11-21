"""Timetable: reusable period definitions and concrete scheduled lectures."""
from __future__ import annotations

from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK
from app.utils.helpers import sql_in

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class TimetablePeriod(UUIDPK, TimestampMixin, Base):
    """A named period template, e.g. 'Period 1 08:30-09:30'."""
    __tablename__ = "timetable_periods"
    __table_args__ = (
        CheckConstraint(
            f"day_of_week IN {sql_in(DAYS)}",
            name="period_day_check",
        ),
    )

    name: Mapped[str] = mapped_column(String(40), nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(12), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    academic_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False
    )


class TimetableEntry(UUIDPK, TimestampMixin, Base):
    """A scheduled lecture — one row of the weekly grid.

    A teacher/class/section/classroom may not have two overlapping entries.
    These constraints are also enforced transactionally in the service layer
    because PostgreSQL range exclusion would need a TSRANGE column; we keep
    the data simple here and validate in the application layer with a SELECT
    ... FOR UPDATE style check inside the create transaction.
    """
    __tablename__ = "timetable_entries"
    __table_args__ = (
        CheckConstraint(
            f"day_of_week IN {sql_in(DAYS)}",
            name="entry_day_check",
        ),
        CheckConstraint("end_time > start_time", name="entry_time_order_check"),
        Index("ix_entry_teacher_day", "teacher_id", "day_of_week"),
        Index("ix_entry_class_day", "class_id", "day_of_week"),
        Index("ix_entry_room_day", "classroom_id", "day_of_week"),
    )

    academic_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    # Optional campus shift filter (morning/evening timetables). Nullable so
    # legacy entries and shift-agnostic schedules remain valid.
    campus_shift_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("campus_shifts.id", ondelete="SET NULL"), nullable=True
    )
    day_of_week: Mapped[str] = mapped_column(String(12), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="RESTRICT"), nullable=False
    )
    section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    classroom_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("classrooms.id", ondelete="SET NULL"), nullable=True
    )
    period_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    teacher = relationship("Teacher", back_populates="timetable_entries")
    subject = relationship("Subject")
    classroom = relationship("Classroom")
    attendance = relationship("AttendanceRecord", back_populates="timetable_entry")
