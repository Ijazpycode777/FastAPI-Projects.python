"""Academic structure: sessions, programs, classes, sections, subjects, departments, assignments."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.database.session import get_db
from app.models.academic import (
    AcademicSession,
    ClassLevel,
    Department,
    Program,
    Section,
    Subject,
)
from app.models.assignments import TeacherAssignment
from app.models.user import User
from app.schemas.academic import (
    AcademicSessionIn,
    AcademicSessionOut,
    AssignmentIn,
    ClassDistributionOut,
    ClassLevelIn,
    ClassLevelOut,
    ClassLevelUpdateIn,
    ClassRosterOut,
    DepartmentOut,
    ProgramIn,
    ProgramOut,
    ProgramUpdateIn,
    SectionIn,
    SectionOut,
    SectionUpdateIn,
    SubjectIn,
    SubjectOut,
    SubjectUpdateIn,
)
from app.security.dependencies import get_current_user, require_admin, require_staff
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


@router.patch("/programs/{program_id}", response_model=ProgramOut, dependencies=[Depends(require_admin())])
async def update_program(program_id: str, payload: ProgramUpdateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.update_program(db, admin, program_id, **payload.model_dump(exclude_unset=True))


@router.delete("/programs/{program_id}", dependencies=[Depends(require_admin())])
async def delete_program(program_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    await academic_service.delete_program(db, admin, program_id)
    return {"message": "Program deleted."}


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


@router.get("/classes/distribution", response_model=list[ClassDistributionOut], dependencies=[Depends(require_admin())])
async def class_distribution(admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    """Aggregated classes view for the Classes Distribution admin page: each
    class with its program, sections, designated subjects and enrolment counts."""
    return await academic_service.list_class_distribution(db)


@router.get("/classes/rosters", response_model=list[ClassDistributionOut], dependencies=[Depends(require_staff())])
async def list_classes_for_roster(user: User = Depends(require_staff()), db: AsyncSession = Depends(get_db)):
    """Role-aware class listing for the Classes Distribution roster feature.

    Admin: every class. Teacher: only classes with an active teacher assignment.
    Students are not permitted (require_staff -> 403). The same
    ClassDistributionOut shape is returned for both roles so the frontend renders
    one listing component.
    """
    return await academic_service.list_classes_for_roster(db, user)


@router.get("/classes/{class_id}/roster", response_model=ClassRosterOut, dependencies=[Depends(require_staff())])
async def get_class_roster(
    class_id: str,
    section_id: str | None = Query(None),
    user: User = Depends(require_staff()),
    db: AsyncSession = Depends(get_db),
):
    """Students currently enrolled in ``class_id`` with a live timetable status.

    Admin: any class. Teacher: only classes they are assigned to -- enforced
    server-side via ``teacher_assigned_to_class`` (403 otherwise), NOT merely by
    hiding the class in the UI, so a teacher cannot reach another teacher's
    roster by editing a URL or API request. Only active enrolments are returned
    (promoted/transferred students are excluded). ``live_status`` is a real-time
    timetable indicator, not attendance.
    """
    cls = await db.get(ClassLevel, class_id)
    if cls is None:
        raise NotFoundError("Class not found.")
    if user.role == "teacher":
        teacher = getattr(user, "teacher_profile", None)
        teacher_id = str(teacher.id) if teacher is not None else None
        if not teacher_id or not await academic_service.teacher_assigned_to_class(db, teacher_id, class_id):
            raise ForbiddenError("You can only view rosters for classes you teach.")
    from app.services.live_status_service import current_now
    return await academic_service.get_class_roster(db, class_id, section_id, current_now())


@router.patch("/classes/{class_id}", response_model=ClassLevelOut, dependencies=[Depends(require_admin())])
async def update_class(class_id: str, payload: ClassLevelUpdateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.update_class(db, admin, class_id, **payload.model_dump(exclude_unset=True))


@router.delete("/classes/{class_id}", dependencies=[Depends(require_admin())])
async def delete_class(class_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    await academic_service.delete_class(db, admin, class_id)
    return {"message": "Class deleted."}


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


@router.patch("/sections/{section_id}", response_model=SectionOut, dependencies=[Depends(require_admin())])
async def update_section(section_id: str, payload: SectionUpdateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.update_section(db, admin, section_id, **payload.model_dump(exclude_unset=True))


@router.delete("/sections/{section_id}", dependencies=[Depends(require_admin())])
async def delete_section(section_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    await academic_service.delete_section(db, admin, section_id)
    return {"message": "Section deleted."}


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


@router.patch("/subjects/{subject_id}", response_model=SubjectOut, dependencies=[Depends(require_admin())])
async def update_subject(subject_id: str, payload: SubjectUpdateIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    return await academic_service.update_subject(db, admin, subject_id, **payload.model_dump(exclude_unset=True))


@router.delete("/subjects/{subject_id}", dependencies=[Depends(require_admin())])
async def delete_subject(subject_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    await academic_service.delete_subject(db, admin, subject_id)
    return {"message": "Subject deleted."}


# ---------------- Departments ----------------
# Read-only list of the five fixed, migration-seeded departments. There is
# intentionally no POST/PATCH/DELETE — departments are not creatable, renamable
# or deletable through the application.
@router.get("/departments", response_model=list[DepartmentOut], dependencies=[Depends(get_current_user)])
async def list_departments(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(Department).order_by(Department.name))
    return list(rows.scalars().all())


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
async def create_assignment(payload: AssignmentIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    assignment = await academic_service.assign_teacher(
        db, admin, payload.teacher_id, payload.subject_id, payload.class_id,
        payload.section_id, payload.academic_session_id,
    )
    return {"id": str(assignment.id), "teacher_id": str(assignment.teacher_id),
            "subject_id": str(assignment.subject_id), "class_id": str(assignment.class_id),
            "section_id": str(assignment.section_id) if assignment.section_id else None}
