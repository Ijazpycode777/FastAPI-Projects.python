"""Academic structure service: sessions, programs, classes, sections, subjects, classrooms.

Also teacher assignments (which teacher teaches what to whom) — the
authoritative source for teacher-side authorization.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.academic import (
    AcademicSession,
    ClassLevel,
    Classroom,
    Program,
    Section,
    Subject,
)
from app.models.assignments import TeacherAssignment
from app.models.people import Teacher
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
async def create_classroom(db, actor, **kw): return await _create(db, actor, Classroom, "classroom.create", **kw)


async def assign_teacher(
    db: AsyncSession, actor, teacher_id: str, subject_id: str, class_id: str,
    section_id: str | None, academic_session_id: str,
) -> TeacherAssignment:
    teacher = await db.get(Teacher, teacher_id)
    if teacher is None:
        raise NotFoundError("Teacher not found.")
    existing = await db.execute(select(TeacherAssignment).where(
        TeacherAssignment.teacher_id == teacher_id,
        TeacherAssignment.subject_id == subject_id,
        TeacherAssignment.class_id == class_id,
        TeacherAssignment.section_id == section_id,
        TeacherAssignment.academic_session_id == academic_session_id,
    ))
    if existing.scalar_one_or_none():
        raise ConflictError("This teacher assignment already exists.")
    return await _create(db, actor, TeacherAssignment, "assignment.create",
                         teacher_id=teacher_id, subject_id=subject_id, class_id=class_id,
                         section_id=section_id, academic_session_id=academic_session_id, is_active=True)


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
