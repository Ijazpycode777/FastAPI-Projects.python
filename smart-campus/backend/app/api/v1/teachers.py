"""Teacher management routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.assignments import TeacherAssignment
from app.models.people import Teacher
from app.models.user import User
from app.schemas.common import Page, paginate
from app.schemas.people import TeacherCreateIn, TeacherOut, TeacherUpdateIn
from app.security.dependencies import require_admin
from app.services import teacher_service

router = APIRouter(prefix="/teachers", tags=["teachers"])


@router.get("", response_model=Page[TeacherOut])
async def list_teachers(
    q: str | None = Query(None),
    department: str | None = Query(None),
    campus_shift_id: str | None = Query(None),
    subject_id: str | None = Query(None),
    status: str | None = Query(None),
    sort: str = Query("created_at", pattern="^(full_name|created_at)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Teacher)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(Teacher.full_name.ilike(like), Teacher.email.ilike(like), Teacher.employee_id.ilike(like)))
    if department:
        stmt = stmt.where(Teacher.department == department)
    if campus_shift_id:
        stmt = stmt.where(Teacher.campus_shift_id == campus_shift_id)
    if status:
        stmt = stmt.where(Teacher.employment_status == status)
    if subject_id:
        sub = select(TeacherAssignment.teacher_id).where(TeacherAssignment.subject_id == subject_id)
        stmt = stmt.where(Teacher.id.in_(sub))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    sort_col = {"full_name": Teacher.full_name, "created_at": Teacher.created_at}[sort]
    stmt = stmt.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    rows = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return paginate([TeacherOut.model_validate(r) for r in rows], page, page_size, int(total or 0))


@router.post("", response_model=TeacherOut, dependencies=[Depends(require_admin())])
async def create_teacher(payload: TeacherCreateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    teacher = await teacher_service.create_teacher(db, admin, payload.model_dump())
    return TeacherOut.model_validate(teacher)


@router.get("/{teacher_id}", response_model=TeacherOut)
async def get_teacher(teacher_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    teacher = await db.get(Teacher, teacher_id)
    if teacher is None:
        raise NotFoundError("Teacher not found.")
    return TeacherOut.model_validate(teacher)


@router.patch("/{teacher_id}", response_model=TeacherOut, dependencies=[Depends(require_admin())])
async def update_teacher(teacher_id: str, payload: TeacherUpdateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    teacher = await db.get(Teacher, teacher_id)
    if teacher is None:
        raise NotFoundError("Teacher not found.")
    teacher = await teacher_service.update_teacher(db, admin, teacher, payload.model_dump(exclude_unset=True))
    return TeacherOut.model_validate(teacher)


@router.post("/{teacher_id}/deactivate", response_model=TeacherOut, dependencies=[Depends(require_admin())])
async def deactivate(teacher_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    teacher = await db.get(Teacher, teacher_id)
    if teacher is None:
        raise NotFoundError("Teacher not found.")
    return TeacherOut.model_validate(await teacher_service.toggle_active(db, admin, teacher, False))


@router.post("/{teacher_id}/activate", response_model=TeacherOut, dependencies=[Depends(require_admin())])
async def activate(teacher_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    teacher = await db.get(Teacher, teacher_id)
    if teacher is None:
        raise NotFoundError("Teacher not found.")
    return TeacherOut.model_validate(await teacher_service.toggle_active(db, admin, teacher, True))
