"""Notices & notifications: publish with audience targeting, dispatch in-app."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, ValidationError
from app.models.communications import Notice, Notification
from app.models.people import Student
from app.models.user import User
from app.repositories.audit import record_audit
from app.services.notifications import AudienceTarget, Recipient, matches


async def _teacher_owns_target(db: AsyncSession, actor, target: dict) -> bool:
    """Teachers may only target classes/sections they're assigned to."""
    from app.models.assignments import TeacherAssignment
    if target["target_audience"] in ("all", "admins", "teachers", "students"):
        return False  # only admins may publish college-wide
    if target["target_audience"] == "program":
        return False
    if target["target_audience"] in ("class", "section"):
        stmt = select(TeacherAssignment).where(
            TeacherAssignment.teacher_id == str(actor.teacher_profile.id),
            TeacherAssignment.class_id == target.get("class_id"),
            TeacherAssignment.is_active.is_(True),
        )
        if target.get("section_id"):
            stmt = stmt.where(
                (TeacherAssignment.section_id == target["section_id"]) | (TeacherAssignment.section_id.is_(None))
            )
        return (await db.execute(stmt)).scalar_one_or_none() is not None
    return False


async def publish(db: AsyncSession, actor, data: dict[str, Any]) -> Notice:
    if actor.role == "teacher" and not await _teacher_owns_target(db, actor, data):
        raise ForbiddenError("Teachers may only publish notices for their own classes/sections.")
    if data["target_audience"] in ("program", "class", "section") and not data.get("class_id") and data["target_audience"] == "class":
        raise ValidationError("Class-targeted notice requires class_id.")
    if data["target_audience"] == "section" and not (data.get("class_id") and data.get("section_id")):
        raise ValidationError("Section-targeted notice requires class_id and section_id.")

    notice = Notice(
        title=data["title"], content=data["content"],
        published_by=actor.id, published_at=datetime.now(timezone.utc),
        target_audience=data["target_audience"],
        program_id=data.get("program_id"), class_id=data.get("class_id"),
        section_id=data.get("section_id"), expires_at=data.get("expires_at"),
        is_pinned=data.get("is_pinned", False),
    )
    db.add(notice)
    await db.flush()

    # Build recipients from current students + staff.
    target = AudienceTarget(data["target_audience"], data.get("program_id"),
                            data.get("class_id"), data.get("section_id"))
    users = (await db.execute(select(User).where(User.is_active.is_(True)))).scalars().all()
    students = (await db.execute(select(Student))).scalars().all()
    by_id = {str(s.user_id): s for s in students}
    recipients = [
        Recipient(str(u.id), u.role,
                  str(by_id[str(u.id)].current_program_id) if str(u.id) in by_id else None,
                  str(by_id[str(u.id)].current_class_id) if str(u.id) in by_id else None,
                  str(by_id[str(u.id)].current_section_id) if str(u.id) in by_id else None)
        for u in users
    ]
    for r in recipients:
        if matches(target, r):
            db.add(Notification(
                user_id=r.user_id, type="notice", title=notice.title,
                body=notice.content[:240], related_resource_type="notice",
                related_resource_id=str(notice.id),
            ))
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="notice.publish", resource_type="notice", resource_id=notice.id)
    await db.commit()
    await db.refresh(notice)
    return notice


async def list_for_user(db: AsyncSession, user: User) -> list[Notice]:
    """Notices visible to a user given their role/placement."""
    stmt = select(Notice)
    if user.role == "admin":
        pass
    elif user.role == "teacher":
        stmt = stmt.where(Notice.target_audience.in_(["all", "teachers"]))
    elif user.role == "student":
        student = user.student_profile
        conds = [Notice.target_audience.in_(["all", "students"])]
        if student and student.current_class_id:
            from sqlalchemy import or_
            conds.append(
                or_(
                    (Notice.target_audience == "class") & (Notice.class_id == student.current_class_id),
                    (Notice.target_audience == "section") & (Notice.class_id == student.current_class_id)
                    & (Notice.section_id == student.current_section_id),
                )
            )
        from sqlalchemy import or_
        stmt = stmt.where(or_(*conds))
    return list((await db.execute(stmt.order_by(Notice.is_pinned.desc(), Notice.published_at.desc()))).scalars().all())


async def notify(db: AsyncSession, user_id: str, *, type_: str, title: str,
                 body: str | None, resource_type: str | None, resource_id: str | None) -> None:
    db.add(Notification(
        user_id=user_id, type=type_, title=title, body=body,
        related_resource_type=resource_type, related_resource_id=resource_id,
    ))
    await db.flush()
