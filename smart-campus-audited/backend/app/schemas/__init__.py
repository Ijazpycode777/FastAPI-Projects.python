from app.schemas.academic import (
    AcademicSessionIn,
    AcademicSessionOut,
    ClassroomIn,
    ClassroomOut,
    ClassLevelIn,
    ClassLevelOut,
    ProgramIn,
    ProgramOut,
    SectionIn,
    SectionOut,
    SubjectIn,
    SubjectOut,
)
from app.schemas.attendance import (
    ATTENDANCE_STATUSES,
    AttendanceBulkIn,
    AttendanceMarkIn,
    AttendanceOut,
    AttendanceSummary,
    AttendanceUpdateIn,
    TeacherAttendanceOut,
    TeacherAttendanceSummary,
)
from app.schemas.audit import AuditLogOut
from app.schemas.auth import (
    CsrfOut,
    LoginIn,
    PasswordChangeIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    ProfileOut,
    ResetPasswordOut,
    UserOut,
)
from app.schemas.common import ErrorResponse, MessageOut, Page, Pagination, paginate
from app.schemas.dashboard import (
    AdminDashboard,
    DistributionPoint,
    SeriesPoint,
    StatCard,
    StudentDashboard,
    TeacherDashboard,
)
from app.schemas.examinations import (
    ExaminationIn,
    ExaminationOut,
    GradeResult,
    GradingBoundaryIn,
    GradingBoundaryOut,
    GradingPolicyIn,
    GradingPolicyOut,
    MarkBulkIn,
    MarkEntryIn,
    MarkUpdateIn,
    StudentMarkOut,
)
from app.schemas.fees import (
    FeeInvoiceOut,
    FeeStructureIn,
    FeeStructureOut,
    InvoiceDetailOut,
    InvoiceGenerateIn,
    PaymentIn,
    PaymentOut,
)
from app.schemas.materials import (
    NoticeIn,
    NoticeOut,
    NotificationOut,
    StudyMaterialCreate,
    StudyMaterialOut,
)
from app.schemas.people import (
    BoardRecordIn,
    BoardRecordOut,
    EnrolmentOut,
    GuardianIn,
    GuardianOut,
    PromoteIn,
    StudentCreateIn,
    StudentDetailOut,
    StudentOut,
    StudentUpdateIn,
    TeacherCreateIn,
    TeacherOut,
    TeacherUpdateIn,
)
from app.schemas.timetable import (
    TimetableEntryDetailOut,
    TimetableEntryIn,
    TimetableEntryOut,
    TimetablePeriodIn,
    TimetablePeriodOut,
)

__all__ = [name for name in dir() if name[0].isupper()]
