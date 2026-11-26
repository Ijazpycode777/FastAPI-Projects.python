"""Academic structure service: sessions, programs, classes, sections, subjects.

Also teacher assignments (which teacher teaches what to whom) — the
authoritative source for teacher-side authorization.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.academic import (
    AcademicSession,
    ClassLevel,
    Program,
    Section,
    Subject,
)
from app.models.assignments import TeacherAssignment
from app.models.attendance import AttendanceRecord
from app.models.examinations import Examination, StudentMark
from app.models.materials import StudyMaterial
from app.models.people import Student, StudentEnrolment, Teacher
from app.models.timetable import TimetableEntry
from app.repositories.audit import record_audit, snapshot


# ---- generic create/update helpers ----
async def _create(db: AsyncSession, actor, model, action: str, **kwargs):
    obj = model(**kwargs)
    db.add(obj)
    await db.flush()
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action=action, resource_type=model.__name__.lower(),
                       resource_id=obj.id, after=await snapshot(obj))
    await db.commit()
    await db.refresh(obj)
    return obj


async def create_session(db, actor, **kw): return await _create(db, actor, AcademicSession, "session.create", **kw)
async def create_program(db, actor, **kw): return await _create(db, actor, Program, "program.create", **kw)
async def create_class(db, actor, **kw): return await _create(db, actor, ClassLevel, "class.create", **kw)
async def create_section(db, actor, **kw): return await _create(db, actor, Section, "section.create", **kw)
async def create_subject(db, actor, **kw): return await _create(db, actor, Subject, "subject.create", **kw)


def _assignment_duplicate_filter(
    teacher_id: str, subject_id: str, class_id: str,
    section_id: str | None, academic_session_id: str,
):
    """WHERE clause matching an existing assignment for the same scope.

    Uses ``section_id.is_(None)`` for the NULL (class-wide) case so the
    comparison actually matches — ``section_id == None`` compiles to
    ``section_id = NULL`` which is always false in SQL and would silently
    bypass the duplicate check for class-wide assignments (D1).
    """
    return (
        TeacherAssignment.teacher_id == teacher_id,
        TeacherAssignment.subject_id == subject_id,
        TeacherAssignment.class_id == class_id,
        (TeacherAssignment.section_id.is_(None) if section_id is None
         else TeacherAssignment.section_id == section_id),
        TeacherAssignment.academic_session_id == academic_session_id,
    )


async def assign_teacher(
    db: AsyncSession, actor, teacher_id: str, subject_id: str, class_id: str,
    section_id: str | None, academic_session_id: str,
) -> TeacherAssignment:
    teacher = await db.get(Teacher, teacher_id)
    if teacher is None:
        raise NotFoundError("Teacher not found.")
    # Pre-check using the NULL-aware filter (D1).
    existing = await db.execute(
        select(TeacherAssignment).where(
            *_assignment_duplicate_filter(
                teacher_id, subject_id, class_id, section_id, academic_session_id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise ConflictError("This teacher assignment already exists.")

    obj = TeacherAssignment(
        teacher_id=teacher_id, subject_id=subject_id, class_id=class_id,
        section_id=section_id, academic_session_id=academic_session_id, is_active=True,
    )
    db.add(obj)
    try:
        await db.flush()
    except IntegrityError as exc:
        # A concurrent assign_teacher for the same scope can race past the
        # pre-check; the partial unique index (D1) then rejects the insert. Map
        # ONLY a genuine duplicate to ConflictError by re-querying: if the row
        # now exists it is a duplicate; otherwise the IntegrityError is
        # unrelated (e.g. a missing FK) and is re-raised so it surfaces
        # accurately rather than being misreported as a duplicate assignment.
        await db.rollback()
        clash = await db.execute(
            select(TeacherAssignment).where(
                *_assignment_duplicate_filter(
                    teacher_id, subject_id, class_id, section_id, academic_session_id
                )
            )
        )
        if clash.scalar_one_or_none() is not None:
            raise ConflictError("This teacher assignment already exists.") from exc
        raise
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="assignment.create", resource_type="teacherassignment",
                       resource_id=obj.id, after=await snapshot(obj))
    await db.commit()
    await db.refresh(obj)
    return obj


async def list_teacher_assignments(db: AsyncSession, teacher_id: str) -> list[TeacherAssignment]:
    result = await db.execute(
        select(TeacherAssignment).where(TeacherAssignment.teacher_id == teacher_id, TeacherAssignment.is_active.is_(True))
    )
    return list(result.scalars().all())


async def teacher_authorized_for(
    db: AsyncSession, teacher_id: str, subject_id: str, class_id: str, section_id: str | None,
    academic_session_id: str | None = None,
) -> bool:
    """The single authorization check used by attendance/marks/materials routes."""
    stmt = select(TeacherAssignment).where(
        TeacherAssignment.teacher_id == teacher_id,
        TeacherAssignment.subject_id == subject_id,
        TeacherAssignment.class_id == class_id,
        TeacherAssignment.is_active.is_(True),
    )
    if section_id is not None:
        stmt = stmt.where(
            (TeacherAssignment.section_id == section_id) | (TeacherAssignment.section_id.is_(None))
        )
    if academic_session_id is not None:
        stmt = stmt.where(TeacherAssignment.academic_session_id == academic_session_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def teacher_assigned_to_class(db: AsyncSession, teacher_id: str, class_id: str) -> bool:
    """True if the teacher has ANY active assignment (any subject/section) for
    the given class. Used to gate class-wide attendance views."""
    result = await db.execute(
        select(TeacherAssignment).where(
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.class_id == class_id,
            TeacherAssignment.is_active.is_(True),
        )
    )
    return result.scalars().first() is not None


# ----------------------------------------------------------------------------
# Classes Distribution: aggregated management view for the admin page.
# ----------------------------------------------------------------------------
async def list_class_distribution(db: AsyncSession) -> list[dict]:
    """Classes with their program, sections, designated subjects (the program's
    subjects) and current enrolment counts — powers the Classes Distribution page."""
    rows = await db.execute(
        select(ClassLevel, Program)
        .join(Program, ClassLevel.program_id == Program.id)
        .order_by(Program.name, ClassLevel.year, ClassLevel.name)
    )
    pairs = rows.all()
    if not pairs:
        return []

    class_ids = [c.id for c, _ in pairs]
    program_ids = list({p.id for _, p in pairs})

    sec_rows = (await db.execute(
        select(Section).where(Section.class_level_id.in_(class_ids)).order_by(Section.name)
    )).scalars().all()
    section_ids = [s.id for s in sec_rows]
    sections_by_class: dict[str, list[Section]] = {}
    for s in sec_rows:
        sections_by_class.setdefault(s.class_level_id, []).append(s)

    subj_rows = (await db.execute(
        select(Subject).where(Subject.program_id.in_(program_ids)).order_by(Subject.name)
    )).scalars().all()
    subjects_by_program: dict[str, list[Subject]] = {}
    for s in subj_rows:
        subjects_by_program.setdefault(s.program_id, []).append(s)

    class_counts = dict((await db.execute(
        select(Student.current_class_id, func.count()).where(Student.current_class_id.in_(class_ids))
        .group_by(Student.current_class_id)
    )).all())
    section_counts: dict = {}
    if section_ids:
        section_counts = dict((await db.execute(
            select(Student.current_section_id, func.count()).where(Student.current_section_id.in_(section_ids))
            .group_by(Student.current_section_id)
        )).all())

    out: list[dict] = []
    for cls, prog in pairs:
        out.append({
            "id": str(cls.id),
            "program_id": str(cls.program_id),
            "program_name": prog.name,
            "program_code": prog.code,
            "name": cls.name,
            "year": cls.year,
            "enrolled": int(class_counts.get(cls.id, 0) or 0),
            "sections": [
                {"id": str(s.id), "name": s.name, "capacity": s.capacity,
                 "enrolled": int(section_counts.get(s.id, 0) or 0)}
                for s in sections_by_class.get(cls.id, [])
            ],
            "subjects": [
                {"id": str(s.id), "code": s.code, "name": s.name}
                for s in subjects_by_program.get(cls.program_id, [])
            ],
        })
    return out


# ----------------------------------------------------------------------------
# Referential-integrity checks for DELETE. Return a human reason if the row is
# referenced by any live data, else None. The DB FK constraints (mostly
# ondelete=RESTRICT) are the final authority; these pre-checks surface a clean
# 409 ConflictError instead of an opaque 500 IntegrityError.
# ----------------------------------------------------------------------------
async def _count(db: AsyncSession, model, *conds) -> int:
    return int((await db.execute(select(func.count(model.id)).where(*conds))).scalar_one() or 0)


async def _class_in_use(db: AsyncSession, class_id: str) -> str | None:
    if await _count(db, StudentEnrolment, StudentEnrolment.class_id == class_id, StudentEnrolment.is_active.is_(True)):
        return "active student enrolments"
    if await _count(db, Student, Student.current_class_id == class_id):
        return "students currently placed in this class"
    if await _count(db, TeacherAssignment, TeacherAssignment.class_id == class_id, TeacherAssignment.is_active.is_(True)):
        return "teacher assignments"
    if await _count(db, Examination, Examination.class_id == class_id):
        return "examinations"
    if await _count(db, StudyMaterial, StudyMaterial.class_id == class_id):
        return "study materials"
    if await _count(db, TimetableEntry, TimetableEntry.class_id == class_id):
        return "timetable entries"
    return None


async def _section_in_use(db: AsyncSession, section_id: str) -> str | None:
    if await _count(db, StudentEnrolment, StudentEnrolment.section_id == section_id, StudentEnrolment.is_active.is_(True)):
        return "active student enrolments"
    if await _count(db, Student, Student.current_section_id == section_id):
        return "students currently placed in this section"
    if await _count(db, TeacherAssignment, TeacherAssignment.section_id == section_id, TeacherAssignment.is_active.is_(True)):
        return "teacher assignments"
    if await _count(db, Examination, Examination.section_id == section_id):
        return "examinations"
    if await _count(db, TimetableEntry, TimetableEntry.section_id == section_id):
        return "timetable entries"
    return None


async def _subject_in_use(db: AsyncSession, subject_id: str) -> str | None:
    if await _count(db, TeacherAssignment, TeacherAssignment.subject_id == subject_id, TeacherAssignment.is_active.is_(True)):
        return "teacher assignments"
    if await _count(db, Examination, Examination.subject_id == subject_id):
        return "examinations"
    if await _count(db, StudentMark, StudentMark.subject_id == subject_id):
        return "student marks"
    if await _count(db, TimetableEntry, TimetableEntry.subject_id == subject_id):
        return "timetable entries"
    if await _count(db, AttendanceRecord, AttendanceRecord.subject_id == subject_id):
        return "attendance records"
    return None


async def _program_in_use(db: AsyncSession, program_id: str) -> str | None:
    if await _count(db, ClassLevel, ClassLevel.program_id == program_id):
        return "classes"
    if await _count(db, Subject, Subject.program_id == program_id):
        return "subjects"
    if await _count(db, Student, Student.current_program_id == program_id):
        return "students currently placed in this program"
    if await _count(db, StudentEnrolment, StudentEnrolment.program_id == program_id, StudentEnrolment.is_active.is_(True)):
        return "active student enrolments"
    return None


# ----------------------------------------------------------------------------
# Updates (rename / resize) with duplicate-name conflict detection.
# ----------------------------------------------------------------------------
async def _audit_and_commit(db: AsyncSession, actor, action: str, resource_type: str, obj) -> None:
    await record_audit(db, actor_id=actor.id, actor_role=actor.role, action=action,
                       resource_type=resource_type, resource_id=obj.id, before=await snapshot(obj))
    await db.commit()


async def update_program(db: AsyncSession, actor, program_id: str, **fields) -> Program:
    prog = await db.get(Program, program_id)
    if prog is None:
        raise NotFoundError("Program not found.")
    if fields.get("code") is not None and fields["code"] != prog.code:
        clash = (await db.execute(select(Program).where(Program.code == fields["code"], Program.id != program_id))).scalar_one_or_none()
        if clash:
            raise ConflictError("A program with that code already exists.")
        prog.code = fields["code"]
    if fields.get("name") is not None:
        prog.name = fields["name"]
    if "description" in fields and fields["description"] is not None:
        prog.description = fields["description"]
    await _audit_and_commit(db, actor, "program.update", "program", prog)
    await db.refresh(prog)
    return prog


async def update_class(db: AsyncSession, actor, class_id: str, **fields) -> ClassLevel:
    cls = await db.get(ClassLevel, class_id)
    if cls is None:
        raise NotFoundError("Class not found.")
    if fields.get("name") is not None and fields["name"] != cls.name:
        clash = (await db.execute(select(ClassLevel).where(
            ClassLevel.program_id == cls.program_id, ClassLevel.name == fields["name"],
            ClassLevel.id != class_id,
        ))).scalar_one_or_none()
        if clash:
            raise ConflictError("A class with that name already exists in this program.")
        cls.name = fields["name"]
    if fields.get("year") is not None:
        cls.year = fields["year"]
    await _audit_and_commit(db, actor, "class.update", "classlevel", cls)
    await db.refresh(cls)
    return cls


async def update_section(db: AsyncSession, actor, section_id: str, **fields) -> Section:
    sec = await db.get(Section, section_id)
    if sec is None:
        raise NotFoundError("Section not found.")
    if fields.get("name") is not None and fields["name"] != sec.name:
        clash = (await db.execute(select(Section).where(
            Section.class_level_id == sec.class_level_id, Section.name == fields["name"],
            Section.id != section_id,
        ))).scalar_one_or_none()
        if clash:
            raise ConflictError("A section with that name already exists in this class.")
        sec.name = fields["name"]
    if fields.get("capacity") is not None:
        sec.capacity = fields["capacity"]
    await _audit_and_commit(db, actor, "section.update", "section", sec)
    await db.refresh(sec)
    return sec


async def update_subject(db: AsyncSession, actor, subject_id: str, **fields) -> Subject:
    subj = await db.get(Subject, subject_id)
    if subj is None:
        raise NotFoundError("Subject not found.")
    if fields.get("code") is not None and fields["code"] != subj.code:
        clash = (await db.execute(select(Subject).where(
            Subject.program_id == subj.program_id, Subject.code == fields["code"],
            Subject.id != subject_id,
        ))).scalar_one_or_none()
        if clash:
            raise ConflictError("A subject with that code already exists in this program.")
        subj.code = fields["code"]
    if fields.get("name") is not None:
        subj.name = fields["name"]
    if fields.get("theory_marks") is not None:
        subj.theory_marks = fields["theory_marks"]
    if fields.get("practical_marks") is not None:
        subj.practical_marks = fields["practical_marks"]
    await _audit_and_commit(db, actor, "subject.update", "subject", subj)
    await db.refresh(subj)
    return subj


# ----------------------------------------------------------------------------
# Deletes — pre-check referential integrity, then delete. A safety-net
# IntegrityError -> ConflictError mapping catches any RESTRICT the pre-check
# missed (e.g. inconsistent legacy data).
# ----------------------------------------------------------------------------
async def _delete(db: AsyncSession, actor, model, resource_id: str, action: str, resource_type: str, in_use_fn):
    obj = await db.get(model, resource_id)
    if obj is None:
        raise NotFoundError(f"{resource_type.capitalize()} not found.")
    reason = await in_use_fn(db, resource_id)
    if reason:
        raise ConflictError(f"Cannot delete this {resource_type} while it has {reason}.")
    await record_audit(db, actor_id=actor.id, actor_role=actor.role, action=action,
                       resource_type=resource_type, resource_id=obj.id, before=await snapshot(obj))
    try:
        await db.delete(obj)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(f"Cannot delete this {resource_type}: it is still referenced.") from exc


async def delete_program(db, actor, program_id):
    return await _delete(db, actor, Program, program_id, "program.delete", "program", _program_in_use)


async def delete_class(db, actor, class_id):
    return await _delete(db, actor, ClassLevel, class_id, "class.delete", "classlevel", _class_in_use)


async def delete_section(db, actor, section_id):
    return await _delete(db, actor, Section, section_id, "section.delete", "section", _section_in_use)


async def delete_subject(db, actor, subject_id):
    return await _delete(db, actor, Subject, subject_id, "subject.delete", "subject", _subject_in_use)
