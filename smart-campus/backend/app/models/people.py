"""People: teachers, guardians, students and their academic history."""
from __future__ import annotations

from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, UniqueConstraint
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
    department: Mapped[str | None] = mapped_column(String(80), nullable=True)
    designation: Mapped[str] = mapped_column(String(80), nullable=False, default="Lecturer")
    joining_date: Mapped[date] = mapped_column(Date, nullable=False)
    employment_status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    # Campus shift this teacher primarily belongs to (nullable for legacy rows).
    campus_shift_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("campus_shifts.id", ondelete="SET NULL"), nullable=True
    )

    user = relationship("User", back_populates="teacher_profile")
    assignments = relationship("TeacherAssignment", back_populates="teacher", cascade="all, delete-orphan")
    attendance = relationship("AttendanceRecord", back_populates="teacher", foreign_keys="AttendanceRecord.teacher_id")
    self_attendance = relationship("TeacherAttendance", back_populates="teacher", cascade="all, delete-orphan")
    timetable_entries = relationship("TimetableEntry", back_populates="teacher")


class Guardian(UUIDPK, TimestampMixin, Base):
    __tablename__ = "guardians"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relationship_type: Mapped[str] = mapped_column(String(40), nullable=False, default="Guardian")
    occupation: Mapped[str | None] = mapped_column(String(80), nullable=True)

    students = relationship("Student", back_populates="guardian")


class Student(UUIDPK, TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("admission_number", name="uq_students_admission_number"),
        # Roll numbers are unique WITHIN a campus shift. The same roll number
        # may be reused in a different shift. NULL shift/roll rows (legacy) are
        # treated as distinct by PostgreSQL/SQLite, so this is safe to add.
        UniqueConstraint("campus_shift_id", "current_roll_number", name="uq_students_shift_roll"),
        CheckConstraint("gender IN ('male','female','other')", name="students_gender_check"),
        CheckConstraint(
            "account_status IN ('active','inactive','graduated','left','suspended')",
            name="students_status_check",
        ),
        Index("ix_students_user", "user_id", unique=True),
        Index("ix_students_admission", "admission_number"),
        Index("ix_students_shift_roll", "campus_shift_id", "current_roll_number"),
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
    account_status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
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
    # Campus shift — every student belongs to a shift (going forward required
    # on create; legacy rows may be NULL until an administrator assigns them).
    campus_shift_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("campus_shifts.id", ondelete="SET NULL"), nullable=True
    )

    user = relationship("User", back_populates="student_profile")
    guardian = relationship("Guardian", back_populates="students", lazy="selectin")
    campus_shift = relationship("CampusShift", back_populates="students")
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
        # Roll-number uniqueness is enforced on the student
        # (campus_shift_id + current_roll_number) so the same roll can be reused
        # across different shifts. The old (session, section, roll) constraint
        # would have blocked that cross-shift reuse, so it is intentionally gone.
        Index("ix_enrolment_student_session", "student_id", "academic_session_id"),
        Index("ix_enrolment_section_roll", "section_id", "roll_number"),
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
    # Snapshot of the student's campus shift at enrolment time.
    campus_shift_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("campus_shifts.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    student = relationship("Student", back_populates="enrolments")
    academic_history = relationship("StudentAcademicHistory", back_populates="enrolment", uselist=False)


class StudentAcademicHistory(UUIDPK, TimestampMixin, Base):
    """Snapshot of placement at the moment of promotion. Preserves previous values."""
    __tablename__ = "student_academic_history"

    student_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    enrolment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("student_enrolments.id", ondelete="CASCADE"), nullable=False
    )
    previous_class: Mapped[str | None] = mapped_column(String(60), nullable=True)
    previous_section: Mapped[str | None] = mapped_column(String(16), nullable=True)
    previous_session: Mapped[str | None] = mapped_column(String(40), nullable=True)
    previous_roll_number: Mapped[int | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # promoted | repeated | section_change | left
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    enrolment = relationship("StudentEnrolment", back_populates="academic_history")


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
