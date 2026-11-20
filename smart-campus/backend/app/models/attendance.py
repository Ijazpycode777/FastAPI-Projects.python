"""Attendance: student lecture attendance + teacher self-attendance.

Student attendance:
  percentage = (present + late) / (present + late + absent) * 100
  excused is excluded from the denominator.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK

STUDENT_STATUSES = ("present", "absent", "late", "excused")
ATTENDED_STATUSES = ("present", "late")


class AttendanceRecord(UUIDPK, TimestampMixin, Base):
    """One row per (student, scheduled lecture, date)."""
    __tablename__ = "attendance_records"
    __table_args__ = (
        CheckConstraint(
            "status IN ('present','absent','late','excused')", name="attendance_status_check"
        ),
        # Prevent duplicate attendance for the same student + scheduled lecture + date.
        UniqueConstraint(
            "student_id",
            "timetable_entry_id",
            "attendance_date",
            name="uq_attendance_student_entry_date",
        ),
        Index("ix_attendance_student_date", "student_id", "attendance_date"),
        Index("ix_attendance_entry_date", "timetable_entry_id", "attendance_date"),
        Index("ix_attendance_class_date", "class_id", "section_id", "attendance_date"),
    )

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    timetable_entry_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("timetable_entries.id", ondelete="CASCADE"), nullable=False
    )
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
    academic_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    marked_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    marked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_finalized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    student = relationship("Student", back_populates="attendance")
    teacher = relationship("Teacher", back_populates="attendance", foreign_keys="AttendanceRecord.teacher_id")
    timetable_entry = relationship("TimetableEntry", back_populates="attendance")
    subject = relationship("Subject")


class TeacherAttendance(UUIDPK, TimestampMixin, Base):
    """Teacher self-attendance: check-in / check-out timestamps (server-generated)."""
    __tablename__ = "teacher_attendance"
    __table_args__ = (
        CheckConstraint("status IN ('present','late','absent')", name="teacher_att_status_check"),
        Index("ix_teacher_att_date", "teacher_id", "attendance_date", unique=True),
    )

    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="absent")
    work_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    teacher = relationship("Teacher", back_populates="self_attendance")


class Holiday(UUIDPK, TimestampMixin, Base):
    """College-wide holidays; excluded from working-day calculations."""
    __tablename__ = "holidays"
    __table_args__ = (UniqueConstraint("date", "academic_session_id", name="uq_holiday_date_session"),)

    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    academic_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="CASCADE"), nullable=False
    )


class LeaveRecord(UUIDPK, TimestampMixin, Base):
    """Leave records for students AND teachers.

    Exactly one of ``student_id`` / ``teacher_id`` is set, matching
    ``person_type``. Leave is a distinct record — never a fake attendance row.
    Admin-submitted leave is stored as ``status='approved'`` with
    ``approved_by`` recording the submitting administrator.
    """
    __tablename__ = "leave_records"
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected')", name="leave_status_check"),
        CheckConstraint("person_type IN ('student','teacher')", name="leave_person_type_check"),
        CheckConstraint(
            "(person_type='student' AND student_id IS NOT NULL AND teacher_id IS NULL) "
            "OR (person_type='teacher' AND teacher_id IS NOT NULL AND student_id IS NULL)",
            name="leave_person_target_check",
        ),
        Index("ix_leave_teacher", "teacher_id", "status"),
        Index("ix_leave_student", "student_id", "status"),
    )

    person_type: Mapped[str] = mapped_column(String(8), nullable=False, default="teacher")
    student_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=True
    )
    teacher_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
