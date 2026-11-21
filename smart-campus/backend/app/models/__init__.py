"""SQLAlchemy 2.0 models for Smart Campus.

All primary keys are UUID v4 strings (String(36)) for portability between
PostgreSQL and the test database. Timestamps are timezone-aware UTC.
"""
from app.database.base import Base, TimestampMixin, UUIDPK
from app.models.academic import AcademicSession, Classroom, ClassLevel, Program, Section, Subject
from app.models.assignments import TeacherAssignment
from app.models.attendance import (
    AttendanceRecord,
    Holiday,
    LeaveRecord,
    TeacherAttendance,
)
from app.models.audit import AuditLog
from app.models.campus import CampusShift, RollNumberScheme
from app.models.communications import Notice, Notification
from app.models.examinations import (
    Examination,
    GradingBoundary,
    GradingPolicy,
    StudentMark,
)
from app.models.fees import FeeInvoice, FeeStructure, Payment
from app.models.materials import StudyMaterial
from app.models.people import (
    BoardExaminationRecord,
    Guardian,
    Student,
    StudentAcademicHistory,
    StudentEnrolment,
    Teacher,
)
from app.models.session import Session
from app.models.timetable import TimetableEntry, TimetablePeriod
from app.models.user import User

__all__ = [
    "Base",
    "UUIDPK",
    "TimestampMixin",
    "User",
    "Session",
    "AcademicSession",
    "Program",
    "ClassLevel",
    "Section",
    "Subject",
    "Classroom",
    "CampusShift",
    "RollNumberScheme",
    "Teacher",
    "Guardian",
    "Student",
    "StudentEnrolment",
    "StudentAcademicHistory",
    "BoardExaminationRecord",
    "TeacherAssignment",
    "TimetablePeriod",
    "TimetableEntry",
    "AttendanceRecord",
    "TeacherAttendance",
    "Holiday",
    "LeaveRecord",
    "Examination",
    "StudentMark",
    "GradingPolicy",
    "GradingBoundary",
    "FeeStructure",
    "FeeInvoice",
    "Payment",
    "StudyMaterial",
    "Notice",
    "Notification",
    "AuditLog",
]
