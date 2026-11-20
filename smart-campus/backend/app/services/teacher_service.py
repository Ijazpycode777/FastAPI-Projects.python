"""Teacher management: create, update, deactivate."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.models.people import Teacher
from app.models.user import User
from app.repositories.audit import record_audit, snapshot
from app.security.password import hash_password


async def create_teacher(db: AsyncSession, actor: User, data: dict[str, Any]) -> Teacher:
    from app.security.password import is_strong_password

    ok, reason = is_strong_password(data["password"])
    if not ok:
        raise ValidationError(reason or "Weak password.")

    email = data["email"].lower().strip()
    if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
        raise ConflictError("A user with that email already exists.")
    if (await db.execute(select(Teacher).where(Teacher.employee_id == data["employee_id"]))).scalar_one_or_none():
        raise ConflictError("Employee ID already in use.")

    user = User(
        email=email,
        role="teacher",
        password_hash=hash_password(data["password"]),
        full_name=data["full_name"],
        phone=data.get("phone"),
        is_active=True,
    )
    db.add(user)
    await db.flush()

    teacher = Teacher(
        user_id=user.id,
        employee_id=data["employee_id"],
        full_name=data["full_name"],
        email=email,
        phone=data.get("phone"),
        department=data.get("department"),
        designation=data.get("designation", "Lecturer"),
        joining_date=data["joining_date"],
        employment_status="active",
    )
    db.add(teacher)
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="teacher.create", resource_type="teacher", resource_id=teacher.id,
        after={"employee_id": teacher.employee_id, "email": email},
    )
    await db.commit()
    await db.refresh(teacher)
    return teacher


async def update_teacher(db: AsyncSession, actor: User, teacher: Teacher, data: dict[str, Any]) -> Teacher:
    before = await snapshot(teacher)
    for k, v in data.items():
        if v is not None:
            setattr(teacher, k, v)
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="teacher.update", resource_type="teacher", resource_id=teacher.id,
        before=before, after=await snapshot(teacher),
    )
    await db.commit()
    await db.refresh(teacher)
    return teacher


async def toggle_active(db: AsyncSession, actor: User, teacher: Teacher, active: bool) -> Teacher:
    teacher.employment_status = "active" if active else "inactive"
    # Explicit UPDATE on the linked user — see note in student_service.toggle_active:
    # ``teacher.user`` is a lazy relationship and must not be navigated under async.
    await db.execute(update(User).where(User.id == teacher.user_id).values(is_active=active))
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action=f"teacher.{'activate' if active else 'deactivate'}",
        resource_type="teacher", resource_id=teacher.id,
    )
    await db.commit()
    await db.refresh(teacher)
    return teacher
