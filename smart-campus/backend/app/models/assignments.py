"""Teacher assignments: which teacher teaches what subject to which class/section."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK


class TeacherAssignment(UUIDPK, TimestampMixin, Base):
    """Authoritative record of a teacher's authority over a subject+class+section.

    All teacher-side authorization checks (attendance marking, marks entry,
    material uploads, notices) consult this table.

    Uniqueness is enforced by TWO partial unique indexes rather than one
    five-column unique constraint, because ``section_id`` is nullable: a single
    UNIQUE constraint treats NULL as distinct on both PostgreSQL and SQLite, so a
    teacher could be silently assigned twice to the same subject+class+session at
    the class-wide (no-section) level. The partial indexes close that gap:

      * ``uq_assignment_classwide``  — WHERE ``section_id IS NULL`` — unique on
        (teacher, subject, class, session): one class-wide assignment per scope.
      * ``uq_assignment_sectioned`` — WHERE ``section_id IS NOT NULL`` — unique
        on (teacher, subject, class, section, session): one per section.
    """
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        # Class-wide assignments (section_id IS NULL): unique per teacher/subject/class/session.
        Index(
            "uq_assignment_classwide",
            "teacher_id", "subject_id", "class_id", "academic_session_id",
            unique=True, postgresql_where=text("section_id IS NULL"),
            sqlite_where=text("section_id IS NULL"),
        ),
        # Section-specific assignments (section_id IS NOT NULL): unique incl. the section.
        Index(
            "uq_assignment_sectioned",
            "teacher_id", "subject_id", "class_id", "section_id", "academic_session_id",
            unique=True, postgresql_where=text("section_id IS NOT NULL"),
            sqlite_where=text("section_id IS NOT NULL"),
        ),
        Index("ix_assignment_teacher", "teacher_id", "is_active"),
        Index("ix_assignment_class_section", "class_id", "section_id"),
    )

    teacher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="RESTRICT"), nullable=False
    )
    section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="RESTRICT"), nullable=True
    )
    academic_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("1"), nullable=False)

    teacher = relationship("Teacher", back_populates="assignments")
    subject = relationship("Subject")
    class_level = relationship("ClassLevel")
    section = relationship("Section")
