"""Examination routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.examinations import Examination, StudentMark
from app.models.user import User
from app.schemas.examinations import (
    ExaminationIn,
    ExaminationOut,
    MarkBulkIn,
    StudentMarkOut,
)
from app.security.dependencies import get_current_user, require_staff
from app.services import exam_service

router = APIRouter(prefix="/examinations", tags=["examinations"])


@router.post("", response_model=ExaminationOut, dependencies=[Depends(require_staff())])
async def create_exam(payload: ExaminationIn, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    exam = await exam_service.create_exam(db, user, payload.model_dump())
    return ExaminationOut.model_validate(exam)


@router.get("", response_model=list[ExaminationOut])
async def list_exams(
    class_id: str | None = Query(None),
    subject_id: str | None = Query(None),
    status: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Examination).order_by(Examination.exam_date.desc())
    if class_id:
        stmt = stmt.where(Examination.class_id == class_id)
    if subject_id:
        stmt = stmt.where(Examination.subject_id == subject_id)
    if status:
        stmt = stmt.where(Examination.status == status)
    rows = (await db.execute(stmt.limit(100))).scalars().all()
    return [ExaminationOut.model_validate(r) for r in rows]


@router.get("/{exam_id}", response_model=ExaminationOut)
async def get_exam(exam_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    exam = await db.get(Examination, exam_id)
    if exam is None:
        raise NotFoundError("Examination not found.")
    return ExaminationOut.model_validate(exam)


@router.post("/{exam_id}/marks", response_model=list[StudentMarkOut], dependencies=[Depends(require_staff())])
async def enter_marks(exam_id: str, payload: MarkBulkIn, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    data = payload.model_dump()
    data["examination_id"] = exam_id
    teacher_id = str(user.teacher_profile.id) if user.role == "teacher" else None
    marks = await exam_service.enter_marks(db, user, teacher_id, data)
    return [StudentMarkOut.model_validate(m) for m in marks]


@router.get("/{exam_id}/marks", response_model=list[StudentMarkOut])
async def list_marks(exam_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(StudentMark).where(StudentMark.examination_id == exam_id))
    return [StudentMarkOut.model_validate(r) for r in rows.scalars().all()]


@router.post("/{exam_id}/publish", response_model=ExaminationOut, dependencies=[Depends(require_staff())])
async def publish(exam_id: str, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    exam = await db.get(Examination, exam_id)
    if exam is None:
        raise NotFoundError("Examination not found.")
    return ExaminationOut.model_validate(await exam_service.publish(db, user, exam))


@router.post("/{exam_id}/finalize", response_model=ExaminationOut, dependencies=[Depends(require_staff())])
async def finalize(exam_id: str, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    exam = await db.get(Examination, exam_id)
    if exam is None:
        raise NotFoundError("Examination not found.")
    return ExaminationOut.model_validate(await exam_service.finalize(db, user, exam))
