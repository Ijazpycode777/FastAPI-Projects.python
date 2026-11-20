"""Examinations, marks, and the versioned grading policy system."""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK
from app.utils.helpers import sql_in

EXAM_TYPES = ("monthly_test", "class_test", "midterm", "final", "quiz")
EXAM_STATUSES = ("draft", "published", "finalized")


class GradingPolicy(UUIDPK, TimestampMixin, Base):
    """A named, versioned grading policy.

    The ``version`` increments each time boundaries are changed; finalized
    results store the policy_id used so changing boundaries for future exams
    never silently rewrites historical results.
    """
    __tablename__ = "grading_policies"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_grading_policy_name_version"),
        Index("ix_grading_policy_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    boundaries = relationship(
        "GradingBoundary", back_populates="policy", cascade="all, delete-orphan",
        lazy="selectin", order_by="GradingBoundary.min_percentage",
    )
    examinations = relationship("Examination", back_populates="grading_policy")


class GradingBoundary(UUIDPK, TimestampMixin, Base):
    """One grade boundary row, e.g. 'A', 90-100, pass."""
    __tablename__ = "grading_boundaries"
    __table_args__ = (
        CheckConstraint("min_percentage >= 0 AND max_percentage <= 100", name="boundary_range_check"),
        CheckConstraint("max_percentage >= min_percentage", name="boundary_order_check"),
        UniqueConstraint("policy_id", "grade_name", name="uq_boundary_policy_grade"),
    )

    policy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("grading_policies.id", ondelete="CASCADE"), nullable=False
    )
    grade_name: Mapped[str] = mapped_column(String(8), nullable=False)
    min_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    max_percentage: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    is_pass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(120), nullable=True)

    policy = relationship("GradingPolicy", back_populates="boundaries")


class Examination(UUIDPK, TimestampMixin, Base):
    """A single examination scoped to subject + class + section."""
    __tablename__ = "examinations"
    __table_args__ = (
        CheckConstraint(f"exam_type IN {sql_in(EXAM_TYPES)}", name="exam_type_check"),
        CheckConstraint(f"status IN {sql_in(EXAM_STATUSES)}", name="exam_status_check"),
        CheckConstraint("max_marks > 0", name="exam_max_marks_check"),
        CheckConstraint("passing_marks >= 0 AND passing_marks <= max_marks", name="exam_passing_marks_check"),
        Index("ix_exam_session_class", "academic_session_id", "class_id", "section_id"),
        Index("ix_exam_subject", "subject_id"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    exam_type: Mapped[str] = mapped_column(String(20), nullable=False)
    academic_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    program_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="RESTRICT"), nullable=False
    )
    section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    max_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    passing_marks: Mapped[int] = mapped_column(Integer, nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft")
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    finalized_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    finalized_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    grading_policy_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("grading_policies.id", ondelete="SET NULL"), nullable=True
    )

    grading_policy = relationship("GradingPolicy", back_populates="examinations")
    marks = relationship("StudentMark", back_populates="examination", cascade="all, delete-orphan")


class StudentMark(UUIDPK, TimestampMixin, Base):
    """One mark row per (examination, student).

    Absent students are represented by ``is_absent=True`` with marks_obtained=0,
    distinct from a student who scored zero.
    """
    __tablename__ = "student_marks"
    __table_args__ = (
        CheckConstraint("marks_obtained >= 0", name="marks_obtained_min_check"),
        Index("ix_marks_exam_student", "examination_id", "student_id", unique=True),
        Index("ix_marks_student_subject", "student_id", "subject_id"),
    )

    examination_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("examinations.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    marks_obtained: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grade: Mapped[str | None] = mapped_column(String(8), nullable=True)
    percentage: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    is_pass: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="entered")  # entered | finalized
    recorded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    recorded_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finalized_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)

    examination = relationship("Examination", back_populates="marks")
    student = relationship("Student", back_populates="marks")
    subject = relationship("Subject")
