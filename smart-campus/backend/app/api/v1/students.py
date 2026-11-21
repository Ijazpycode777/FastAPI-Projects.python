"""Student management routes (admin) + student self-service."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.database.session import get_db
from app.models.academic import AcademicSession, ClassLevel, Program, Section
from app.models.people import Student
from app.models.user import User
from app.schemas.common import Page, paginate
from app.schemas.people import (
    BoardRecordIn,
    BoardRecordOut,
    PromoteIn,
    StudentCreateIn,
    StudentDetailOut,
    StudentOut,
    StudentUpdateIn,
)
from app.security.dependencies import get_current_user, require_admin, require_student
from app.services import student_service

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=Page[StudentOut])
async def list_students(
    q: str | None = Query(None),
    program_id: str | None = Query(None),
    class_id: str | None = Query(None),
    section_id: str | None = Query(None),
    session_id: str | None = Query(None),
    status: str | None = Query(None),
    sort: str = Query("created_at", pattern="^(full_name|roll|created_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Student)
    if q:
        like = f"%{q.lower()}%"
        conds = [Student.full_name.ilike(like), Student.admission_number.ilike(like), Student.email.ilike(like)]
        if q.strip().isdigit():
            conds.append(Student.current_roll_number == int(q.strip()))
        stmt = stmt.where(or_(*conds))
    if program_id:
        stmt = stmt.where(Student.current_program_id == program_id)
    if class_id:
        stmt = stmt.where(Student.current_class_id == class_id)
    if section_id:
        stmt = stmt.where(Student.current_section_id == section_id)
    if session_id:
        stmt = stmt.where(Student.current_session_id == session_id)
    if status:
        stmt = stmt.where(Student.account_status == status)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    sort_col = {"full_name": Student.full_name, "roll": Student.current_roll_number, "created_at": Student.created_at}[sort]
    stmt = stmt.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    rows = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return paginate([StudentOut.model_validate(r) for r in rows], page, page_size, int(total or 0))


@router.post("", response_model=StudentOut, dependencies=[Depends(require_admin())])
async def create_student(payload: StudentCreateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    student = await student_service.create_student(db, admin, payload.model_dump())
    return StudentOut.model_validate(student)


@router.get("/{student_id}", response_model=StudentDetailOut)
async def get_student(student_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "student" and str(user.student_profile.id) != str(student_id):
        raise ForbiddenError("You can only view your own profile.")
    student = await db.get(Student, student_id)
    if student is None:
        raise NotFoundError("Student not found.")
    out = StudentDetailOut.model_validate(student)
    # Resolve the placement names so the edit form can prefill them as free text.
    if student.current_program_id and (p := await db.get(Program, student.current_program_id)):
        out.program_name = p.name
    if student.current_class_id and (c := await db.get(ClassLevel, student.current_class_id)):
        out.class_name = c.name
    if student.current_section_id and (s := await db.get(Section, student.current_section_id)):
        out.section_name = s.name
    if student.current_session_id and (sess := await db.get(AcademicSession, student.current_session_id)):
        out.session_name = sess.name
    return out


@router.patch("/{student_id}", response_model=StudentOut, dependencies=[Depends(require_admin())])
async def update_student(student_id: str, payload: StudentUpdateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if student is None:
        raise NotFoundError("Student not found.")
    student = await student_service.update_student(db, admin, student, payload.model_dump(exclude_unset=True))
    return StudentOut.model_validate(student)


@router.post("/{student_id}/deactivate", response_model=StudentOut, dependencies=[Depends(require_admin())])
async def deactivate(student_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if student is None:
        raise NotFoundError("Student not found.")
    return StudentOut.model_validate(await student_service.toggle_active(db, admin, student, False))


@router.post("/{student_id}/activate", response_model=StudentOut, dependencies=[Depends(require_admin())])
async def activate(student_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    student = await db.get(Student, student_id)
    if student is None:
        raise NotFoundError("Student not found.")
    return StudentOut.model_validate(await student_service.toggle_active(db, admin, student, True))


@router.post("/promote", response_model=StudentOut, dependencies=[Depends(require_admin())])
async def promote(payload: PromoteIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    student = await student_service.promote(db, admin, payload.model_dump())
    return StudentOut.model_validate(student)


# ---------------- Board records ----------------
@router.post("/{student_id}/board-records", response_model=BoardRecordOut, dependencies=[Depends(require_admin())])
async def add_board_record(student_id: str, payload: BoardRecordIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    from app.models.people import BoardExaminationRecord
    student = await db.get(Student, student_id)
    if student is None:
        raise NotFoundError("Student not found.")
    rec = BoardExaminationRecord(student_id=student_id, level=payload.level, board=payload.board,
                                 examination_year=payload.examination_year, total_marks=payload.total_marks,
                                 obtained_marks=payload.obtained_marks, grade=payload.grade)
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return BoardRecordOut.model_validate(rec)


@router.get("/{student_id}/board-records", response_model=list[BoardRecordOut])
async def list_board_records(student_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "student" and str(user.student_profile.id) != str(student_id):
        raise ForbiddenError("You can only view your own records.")
    from app.models.people import BoardExaminationRecord
    rows = await db.execute(select(BoardExaminationRecord).where(BoardExaminationRecord.student_id == student_id))
    return [BoardRecordOut.model_validate(r) for r in rows.scalars().all()]


# ---------------- Student self: attendance / results / fees ----------------
@router.get("/me/attendance", tags=["student-self"])
async def my_attendance(user: User = Depends(require_student()), db: AsyncSession = Depends(get_db)):
    from app.services.attendance_service import student_percentage
    return await student_percentage(db, str(user.student_profile.id))
