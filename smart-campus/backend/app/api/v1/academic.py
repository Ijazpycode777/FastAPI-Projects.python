"""Academic structure: sessions, programs, classes, sections, subjects, classrooms, assignments."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.academic import (
    AcademicSession,
    ClassLevel,
    Classroom,
    Program,
    Section,
    Subject,
)
from app.models.assignments import TeacherAssignment
from app.models.user import User
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
from app.security.dependencies import get_current_user, require_admin
from app.services import academic_service

router = APIRouter(tags=["academic"])


# ---------------- Sessions ----------------
@router.get("/sessions", response_model=list[AcademicSessionOut], dependencies=[Depends(get_current_user)])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(AcademicSession).order_by(AcademicSession.start_date.desc()))
    return list(rows.scalars().all())


@router.post("/sessions", response_model=AcademicSessionOut, dependencies=[Depends(require_admin())])
async def create_session(payload: AcademicSessionIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.create_session(db, admin, name=payload.name, start_date=payload.start_date,
                                                 end_date=payload.end_date, is_active=payload.is_active)


# ---------------- Programs ----------------
@router.get("/programs", response_model=list[ProgramOut], dependencies=[Depends(get_current_user)])
async def list_programs(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(Program).order_by(Program.name))
    return list(rows.scalars().all())


@router.post("/programs", response_model=ProgramOut, dependencies=[Depends(require_admin())])
async def create_program(payload: ProgramIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.create_program(db, admin, code=payload.code, name=payload.name, description=payload.description)


# ---------------- Classes ----------------
@router.get("/classes", response_model=list[ClassLevelOut], dependencies=[Depends(get_current_user)])
async def list_classes(program_id: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(ClassLevel).order_by(ClassLevel.year)
    if program_id:
        stmt = stmt.where(ClassLevel.program_id == program_id)
    return list((await db.execute(stmt)).scalars().all())


@router.post("/classes", response_model=ClassLevelOut, dependencies=[Depends(require_admin())])
async def create_class(payload: ClassLevelIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.create_class(db, admin, program_id=payload.program_id, name=payload.name, year=payload.year)


# ---------------- Sections ----------------
@router.get("/sections", response_model=list[SectionOut], dependencies=[Depends(get_current_user)])
async def list_sections(class_level_id: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(Section).order_by(Section.name)
    if class_level_id:
        stmt = stmt.where(Section.class_level_id == class_level_id)
    return list((await db.execute(stmt)).scalars().all())


@router.post("/sections", response_model=SectionOut, dependencies=[Depends(require_admin())])
async def create_section(payload: SectionIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.create_section(db, admin, class_level_id=payload.class_level_id,
                                                 name=payload.name, capacity=payload.capacity)


# ---------------- Subjects ----------------
@router.get("/subjects", response_model=list[SubjectOut], dependencies=[Depends(get_current_user)])
async def list_subjects(program_id: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(Subject).order_by(Subject.name)
    if program_id:
        stmt = stmt.where(Subject.program_id == program_id)
    return list((await db.execute(stmt)).scalars().all())


@router.post("/subjects", response_model=SubjectOut, dependencies=[Depends(require_admin())])
async def create_subject(payload: SubjectIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.create_subject(db, admin, program_id=payload.program_id, code=payload.code,
                                                 name=payload.name, theory_marks=payload.theory_marks,
                                                 practical_marks=payload.practical_marks)


# ---------------- Classrooms ----------------
@router.get("/classrooms", response_model=list[ClassroomOut], dependencies=[Depends(get_current_user)])
async def list_classrooms(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(Classroom).where(Classroom.is_active.is_(True)).order_by(Classroom.room_number))
    return list(rows.scalars().all())


@router.post("/classrooms", response_model=ClassroomOut, dependencies=[Depends(require_admin())])
async def create_classroom(payload: ClassroomIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.create_classroom(db, admin, room_number=payload.room_number, building=payload.building,
                                                    capacity=payload.capacity, is_active=payload.is_active)


# ---------------- Teacher assignments ----------------
@router.get("/assignments", tags=["assignments"], dependencies=[Depends(get_current_user)])
async def list_assignments(teacher_id: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = select(TeacherAssignment).where(TeacherAssignment.is_active.is_(True))
    if teacher_id:
        stmt = stmt.where(TeacherAssignment.teacher_id == teacher_id)
    rows = (await db.execute(stmt)).scalars().all()
    return [{"id": str(a.id), "teacher_id": str(a.teacher_id), "subject_id": str(a.subject_id),
             "class_id": str(a.class_id), "section_id": str(a.section_id),
             "academic_session_id": str(a.academic_session_id)} for a in rows]


@router.post("/assignments", tags=["assignments"], dependencies=[Depends(require_admin())])
async def create_assignment(payload: dict, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    assignment = await academic_service.assign_teacher(
        db, admin, payload["teacher_id"], payload["subject_id"], payload["class_id"],
        payload.get("section_id"), payload["academic_session_id"],
    )
    return {"id": str(assignment.id), "teacher_id": str(assignment.teacher_id),
            "subject_id": str(assignment.subject_id), "class_id": str(assignment.class_id),
            "section_id": str(assignment.section_id) if assignment.section_id else None}
