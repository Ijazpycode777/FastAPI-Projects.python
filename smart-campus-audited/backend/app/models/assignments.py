"""Teacher assignments: which teacher teaches what subject to which class/section."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK


class TeacherAssignment(UUIDPK, TimestampMixin, Base):
    """Authoritative record of a teacher's authority over a subject+class+section.

    All teacher-side authorization checks (attendance marking, marks entry,
    material uploads, notices) consult this table.
    """
    __tablename__ = "teacher_assignments"
    __table_args__ = (
        UniqueConstraint(
            "teacher_id",
            "subject_id",
            "class_id",
            "section_id",
            "academic_session_id",
            name="uq_assignment_teacher_subject_class_section_session",
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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    teacher = relationship("Teacher", back_populates="assignments")
    subject = relationship("Subject")
    class_level = relationship("ClassLevel")
    section = relationship("Section")
