"""Timetable routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.timetable import TimetableEntry, TimetablePeriod
from app.models.user import User
from app.schemas.timetable import (
    TimetableEntryDetailOut,
    TimetableEntryIn,
    TimetableEntryOut,
    TimetableEntryUpdateIn,
    TimetablePeriodIn,
    TimetablePeriodOut,
)
from app.security.dependencies import get_current_user, require_admin, require_staff
from app.services import timetable_service

router = APIRouter(prefix="/timetable", tags=["timetable"])


@router.post("/periods", response_model=TimetablePeriodOut, dependencies=[Depends(require_admin())])
async def create_period(payload: TimetablePeriodIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await timetable_service.create_period(db, admin, **payload.model_dump())


@router.get("/periods", response_model=list[TimetablePeriodOut], dependencies=[Depends(get_current_user)])
async def list_periods(academic_session_id: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(TimetablePeriod).order_by(TimetablePeriod.day_of_week, TimetablePeriod.start_time)
    if academic_session_id:
        stmt = stmt.where(TimetablePeriod.academic_session_id == academic_session_id)
    return list((await db.execute(stmt)).scalars().all())


@router.post("/entries", response_model=TimetableEntryOut, dependencies=[Depends(require_staff())])
async def create_entry(payload: TimetableEntryIn, user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    entry = await timetable_service.create_entry(db, user, payload.model_dump())
    return TimetableEntryOut.model_validate(entry)


@router.get("/entries", response_model=list[TimetableEntryDetailOut], dependencies=[Depends(get_current_user)])
async def list_entries(
    teacher_id: str | None = Query(None),
    class_id: str | None = Query(None),
    section_id: str | None = Query(None),
    academic_session_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(TimetableEntry)
        .options(selectinload(TimetableEntry.teacher),
                 selectinload(TimetableEntry.subject),
                 selectinload(TimetableEntry.classroom))
        .where(TimetableEntry.is_cancelled.is_(False))
        .order_by(TimetableEntry.day_of_week, TimetableEntry.start_time)
    )
    if teacher_id:
        stmt = stmt.where(TimetableEntry.teacher_id == teacher_id)
    if class_id:
        stmt = stmt.where(TimetableEntry.class_id == class_id)
    if section_id:
        stmt = stmt.where((TimetableEntry.section_id == section_id) | (TimetableEntry.section_id.is_(None)))
    if academic_session_id:
        stmt = stmt.where(TimetableEntry.academic_session_id == academic_session_id)
    rows = (await db.execute(stmt)).scalars().all()
    out = []
    for e in rows:
        d = TimetableEntryDetailOut.model_validate(e)
        d.subject_name = e.subject.name if e.subject else None
        d.teacher_name = e.teacher.full_name if e.teacher else None
        d.classroom_number = e.classroom.room_number if e.classroom else None
        out.append(d)
    return out


@router.post("/entries/{entry_id}/cancel", response_model=TimetableEntryOut, dependencies=[Depends(require_admin())])
async def cancel_entry(entry_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    entry = await db.get(TimetableEntry, entry_id)
    if entry is None:
        raise NotFoundError("Timetable entry not found.")
    return TimetableEntryOut.model_validate(await timetable_service.cancel_entry(db, admin, entry))


@router.patch("/entries/{entry_id}", response_model=TimetableEntryOut, dependencies=[Depends(require_admin())])
async def update_entry(entry_id: str, payload: TimetableEntryUpdateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    entry = await db.get(TimetableEntry, entry_id)
    if entry is None:
        raise NotFoundError("Timetable entry not found.")
    return TimetableEntryOut.model_validate(await timetable_service.update_entry(db, admin, entry, payload.model_dump(exclude_unset=True)))


@router.delete("/entries/{entry_id}", status_code=204, dependencies=[Depends(require_admin())])
async def delete_entry(entry_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    entry = await db.get(TimetableEntry, entry_id)
    if entry is None:
        raise NotFoundError("Timetable entry not found.")
    await timetable_service.delete_entry(db, admin, entry)


@router.get("/me", tags=["timetable-self"], dependencies=[Depends(get_current_user)])
async def my_timetable(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if user.role == "teacher":
        rows = await timetable_service.weekly_for_teacher(db, str(user.teacher_profile.id))
    elif user.role == "student":
        s = user.student_profile
        rows = await timetable_service.weekly_for_class(db, str(s.current_class_id), str(s.current_section_id) if s.current_section_id else None)
    else:
        rows = []
    return [{"id": str(e.id), "day": e.day_of_week, "start": e.start_time.isoformat(),
             "end": e.end_time.isoformat(), "subject_id": str(e.subject_id),
             "class_id": str(e.class_id), "teacher_id": str(e.teacher_id),
             "classroom_id": str(e.classroom_id) if e.classroom_id else None} for e in rows]
