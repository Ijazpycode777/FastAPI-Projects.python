"""Academic structure: sessions, programs, classes/parts, sections, subjects, classrooms.

Hierarchy: College → AcademicSession → Program → ClassLevel → Section → Subject.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK


class AcademicSession(UUIDPK, TimestampMixin, Base):
    """An academic year, e.g. 2024-2025."""
    __tablename__ = "academic_sessions"
    __table_args__ = (
        UniqueConstraint("name", name="uq_academic_sessions_name"),
        Index("ix_academic_sessions_active", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(40), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Program(UUIDPK, TimestampMixin, Base):
    """e.g. ICS, FSc, I.Com."""
    __tablename__ = "programs"
    __table_args__ = (UniqueConstraint("code", name="uq_programs_code"),)

    code: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    classes = relationship("ClassLevel", back_populates="program", cascade="all, delete-orphan")
    subjects = relationship("Subject", back_populates="program", cascade="all, delete-orphan")


class ClassLevel(UUIDPK, TimestampMixin, Base):
    """A part/year of a program, e.g. 'ICS Part 1'."""
    __tablename__ = "class_levels"
    __table_args__ = (
        UniqueConstraint("program_id", "name", name="uq_class_level_program_name"),
    )

    program_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)  # e.g. "Part 1"
    year: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2

    program = relationship("Program", back_populates="classes")
    sections = relationship("Section", back_populates="class_level", cascade="all, delete-orphan")


class Section(UUIDPK, TimestampMixin, Base):
    """A section within a class, e.g. 'A'."""
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("class_level_id", "name", name="uq_section_class_name"),
    )

    class_level_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(16), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=40)

    class_level = relationship("ClassLevel", back_populates="sections")


class Subject(UUIDPK, TimestampMixin, Base):
    """A subject offered by a program."""
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("program_id", "code", name="uq_subject_program_code"),
    )

    program_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(24), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    theory_marks: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    practical_marks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    program = relationship("Program", back_populates="subjects")


class Classroom(UUIDPK, TimestampMixin, Base):
    """A physical room."""
    __tablename__ = "classrooms"
    __table_args__ = (UniqueConstraint("room_number", name="uq_classrooms_room_number"),)

    room_number: Mapped[str] = mapped_column(String(24), nullable=False)
    building: Mapped[str | None] = mapped_column(String(80), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
