"""People: teachers, guardians, students and their academic history."""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK


class Teacher(UUIDPK, TimestampMixin, Base):
    __tablename__ = "teachers"
    __table_args__ = (
        UniqueConstraint("employee_id", name="uq_teachers_employee_id"),
        Index("ix_teachers_user", "user_id", unique=True),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[str] = mapped_column(String(32), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # Exactly one fixed department (FK to the migration-seeded five rows).
    department_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False
    )
    # Exactly one manually entered subject (free text — no catalogue, no
    # department→subject mapping, no compatibility checks).
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    designation: Mapped[str] = mapped_column(String(80), nullable=False, default="Lecturer", server_default="Lecturer")
    joining_date: Mapped[date] = mapped_column(Date, nullable=False)
    employment_status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", server_default="active")

    user = relationship("User", back_populates="teacher_profile")
    # Eager-loaded so ``teacher.department.name`` is safe under async without an
    # explicit selectinload at every call site (departments is a tiny fixed set).
    department = relationship("Department", lazy="selectin")
    assignments = relationship("TeacherAssignment", back_populates="teacher", cascade="all, delete-orphan")
    attendance = relationship("AttendanceRecord", back_populates="teacher", foreign_keys="AttendanceRecord.teacher_id")
    self_attendance = relationship("TeacherAttendance", back_populates="teacher", cascade="all, delete-orphan")
    timetable_entries = relationship("TimetableEntry", back_populates="teacher")

    @property
    def department_name(self) -> str | None:
        """Resolved department name for API serialization (TeacherOut)."""
        return self.department.name if self.department is not None else None


class Guardian(UUIDPK, TimestampMixin, Base):
    __tablename__ = "guardians"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False, default="Guardian", server_default="Guardian")
    occupation: Mapped[str | None] = mapped_column(String(80), nullable=True)

    students = relationship("Student", back_populates="guardian")


class Student(UUIDPK, TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("admission_number", name="uq_students_admission_number"),
        CheckConstraint("gender IN ('male','female','other')", name="students_gender_check"),
        CheckConstraint(
            "account_status IN ('active','inactive','graduated','left','suspended')",
            name="students_status_check",
        ),
        Index("ix_students_user", "user_id", unique=True),
        Index("ix_students_admission", "admission_number"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    admission_number: Mapped[str] = mapped_column(String(32), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)
    guardian_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("guardians.id", ondelete="SET NULL"), nullable=True
    )
    admission_date: Mapped[date] = mapped_column(Date, nullable=False)
    account_status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", server_default="active")
    # Current placement pointers (mutated on promotion; history kept in enrolments)
    current_program_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("programs.id", ondelete="SET NULL"), nullable=True
    )
    current_class_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="SET NULL"), nullable=True
    )
    current_section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    current_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True
    )
    current_roll_number: Mapped[int | None] = mapped_column(nullable=True)

    user = relationship("User", back_populates="student_profile")
    guardian = relationship("Guardian", back_populates="students", lazy="selectin")
    enrolments = relationship("StudentEnrolment", back_populates="student", cascade="all, delete-orphan")
    board_records = relationship("BoardExaminationRecord", back_populates="student", cascade="all, delete-orphan")
    attendance = relationship("AttendanceRecord", back_populates="student")
    marks = relationship("StudentMark", back_populates="student")


class StudentEnrolment(UUIDPK, TimestampMixin, Base):
    """One enrolment row per (student, academic session). Preserves history.

    When a student is promoted, the previous enrolment's ``is_active`` flag is
    set to False (never deleted) and a new enrolment row is inserted.
    """
    __tablename__ = "student_enrolments"
    __table_args__ = (
        # Roll numbers are unique across the ENTIRE academic session — two
        # students in the same session can never share a roll number, even in
        # different sections, classes or programs. The same roll may be reused
        # in a different session.
        UniqueConstraint(
            "academic_session_id", "roll_number",
            name="uq_enrolment_session_roll",
        ),
        # A student has at most one enrolment record per academic session.
        UniqueConstraint(
            "student_id", "academic_session_id",
            name="uq_enrolment_student_session",
        ),
        Index("ix_enrolment_section_roll", "section_id", "roll_number"),
        # D18: supports the common "find this student's active enrolment" lookup
        # used by student_service / dashboard / report queries.
        Index("ix_enrolment_student_active", "student_id", "is_active"),
        # D8: a student has at most ONE active enrolment across all sessions.
        # The promote/update flows always deactivate the previous enrolment
        # before creating the new one inside the same transaction, so this
        # partial unique index is safe. Enforced via a partial index because a
        # plain UNIQUE(student_id) would also forbid the historical inactive rows.
        Index(
            "uq_enrolment_one_active", "student_id", unique=True,
            postgresql_where=text("is_active"), sqlite_where=text("is_active"),
        ),
    )

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    academic_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    program_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="RESTRICT"), nullable=False
    )
    section_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="RESTRICT"), nullable=False
    )
    roll_number: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("1"), nullable=False)

    student = relationship("Student", back_populates="enrolments")
    academic_history = relationship("StudentAcademicHistory", back_populates="enrolment", uselist=False)


class StudentAcademicHistory(UUIDPK, TimestampMixin, Base):
    """Snapshot of placement at the moment of promotion. Preserves previous values.

    ``enrolment_id`` points to the NEW enrolment created by the promotion (the
    one-to-one partner), NOT the previous one. The ``previous_*`` text fields
    hold the OLD placement identifiers captured before the old enrolment was
    deactivated. The nullable ``previous_*_id`` foreign keys (D2) are the
    relational form of those old identifiers: they are backfilled from the
    ``previous_*`` text columns (NOT from ``enrolment_id``) and only where the
    referenced row still exists; ``ON DELETE SET NULL`` keeps the history row
    alive if a referenced class/section/session is later deleted (the text
    snapshot remains as a fallback label).
    """
    __tablename__ = "student_academic_history"
    __table_args__ = (
        # One-to-one with StudentEnrolment: each enrolment has at most one
        # history snapshot (matches the uselist=False relationship below).
        UniqueConstraint("enrolment_id", name="uq_academic_history_enrolment"),
    )

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    enrolment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_enrolments.id", ondelete="CASCADE"), nullable=False
    )
    # Previous placement — free-text snapshots (kept for resilience when a
    # referenced row is deleted/renamed; these are the OLD ids as strings).
    previous_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    previous_section: Mapped[str | None] = mapped_column(String(16), nullable=True)
    previous_session: Mapped[str | None] = mapped_column(String(40), nullable=True)
    previous_roll_number: Mapped[int | None] = mapped_column(nullable=True)
    # D2: relational form of the previous placement. Nullable + ON DELETE SET
    # NULL so the history row survives parent deletion (text snapshot remains).
    previous_class_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="SET NULL"), nullable=True
    )
    previous_section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    previous_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("academic_sessions.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # promoted | repeated | section_change | left
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    enrolment = relationship("StudentEnrolment", back_populates="academic_history")
    previous_class_level = relationship("ClassLevel", foreign_keys=[previous_class_id])
    previous_section_ref = relationship("Section", foreign_keys=[previous_section_id])
    previous_session_ref = relationship("AcademicSession", foreign_keys=[previous_session_id])


class BoardExaminationRecord(UUIDPK, TimestampMixin, Base):
    """Previous (external board) exam records, separate from college exams.

    Levels: matric | inter_part1
    """
    __tablename__ = "board_examination_records"
    __table_args__ = (
        CheckConstraint("level IN ('matric','inter_part1')", name="board_level_check"),
        UniqueConstraint("student_id", "level", name="uq_board_record_student_level"),
        Index("ix_board_record_student", "student_id"),
    )

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    board: Mapped[str] = mapped_column(String(120), nullable=False)
    examination_year: Mapped[int] = mapped_column(nullable=False)
    total_marks: Mapped[int] = mapped_column(nullable=False)
    obtained_marks: Mapped[int] = mapped_column(nullable=False)
    grade: Mapped[str | None] = mapped_column(String(4), nullable=True)

    student = relationship("Student", back_populates="board_records")

    @property
    def percentage(self) -> float:
        if self.total_marks <= 0:
            return 0.0
        return round((self.obtained_marks / self.total_marks) * 100, 2)
