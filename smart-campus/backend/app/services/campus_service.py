"""Campus shift + roll-number scheme management (administrator only)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.academic import ClassLevel, Section
from app.models.campus import CampusShift, RollNumberScheme
from app.repositories.audit import record_audit


# ---------------- Campus shifts ----------------
async def list_shifts(db: AsyncSession) -> list[CampusShift]:
    return list((await db.execute(select(CampusShift).order_by(CampusShift.name))).scalars().all())


async def create_shift(db: AsyncSession, actor, data: dict[str, Any]) -> CampusShift:
    code = data["code"].strip()
    clash = await db.execute(select(CampusShift).where(func.lower(CampusShift.code) == code.lower()))
    if clash.scalar_one_or_none():
        raise ConflictError(f"Campus shift with code '{code}' already exists.")
    rec = CampusShift(
        name=data["name"].strip(), code=code,
        start_time=data.get("start_time"), end_time=data.get("end_time"),
        is_active=data.get("is_active", True),
    )
    db.add(rec)
    await db.flush()
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="shift.create", resource_type="campus_shift", resource_id=rec.id,
        after={"name": rec.name, "code": rec.code},
    )
    await db.commit()
    await db.refresh(rec)
    return rec


async def update_shift(db: AsyncSession, actor, rec: CampusShift, data: dict[str, Any]) -> CampusShift:
    before = {"name": rec.name, "code": rec.code, "is_active": rec.is_active}
    for k in ("name", "code", "start_time", "end_time", "is_active"):
        if data.get(k) is not None:
            setattr(rec, k, data[k])
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="shift.update", resource_type="campus_shift", resource_id=rec.id,
        before=before, after={"name": rec.name, "code": rec.code, "is_active": rec.is_active},
    )
    await db.commit()
    await db.refresh(rec)
    return rec


# ---------------- Roll-number schemes ----------------
async def list_schemes(
    db: AsyncSession, campus_shift_id: str | None = None, class_id: str | None = None
) -> list[RollNumberScheme]:
    stmt = select(RollNumberScheme)
    if campus_shift_id:
        stmt = stmt.where(RollNumberScheme.campus_shift_id == campus_shift_id)
    if class_id:
        stmt = stmt.where(RollNumberScheme.class_id == class_id)
    stmt = stmt.order_by(RollNumberScheme.min_roll)
    return list((await db.execute(stmt)).scalars().all())


async def create_scheme(db: AsyncSession, actor, data: dict[str, Any]) -> RollNumberScheme:
    if await db.get(CampusShift, data["campus_shift_id"]) is None:
        raise NotFoundError("Campus shift not found.")
    if await db.get(ClassLevel, data["class_id"]) is None:
        raise NotFoundError("Class not found.")
    section_id = data.get("section_id")
    if section_id and await db.get(Section, section_id) is None:
        raise NotFoundError("Section not found.")
    stmt = select(RollNumberScheme).where(
        RollNumberScheme.campus_shift_id == data["campus_shift_id"],
        RollNumberScheme.class_id == data["class_id"],
        or_(RollNumberScheme.section_id == section_id, RollNumberScheme.section_id.is_(None)),
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        raise ConflictError("A roll-number scheme already exists for this shift/class/section.")
    rec = RollNumberScheme(
        campus_shift_id=data["campus_shift_id"], class_id=data["class_id"],
        section_id=section_id, prefix=data.get("prefix"),
        min_roll=data["min_roll"], max_roll=data["max_roll"], padding=data.get("padding", 2),
    )
    db.add(rec)
    await db.flush()
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="roll_scheme.create", resource_type="roll_number_scheme", resource_id=rec.id,
        after={"class_id": rec.class_id, "min": rec.min_roll, "max": rec.max_roll},
    )
    await db.commit()
    await db.refresh(rec)
    return rec


async def update_scheme(db: AsyncSession, actor, rec: RollNumberScheme, data: dict[str, Any]) -> RollNumberScheme:
    for k in ("prefix", "min_roll", "max_roll", "padding", "section_id"):
        if data.get(k) is not None:
            setattr(rec, k, data[k])
    if rec.max_roll < rec.min_roll:
        raise ValidationError("max_roll must be >= min_roll.")
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="roll_scheme.update", resource_type="roll_number_scheme", resource_id=rec.id,
    )
    await db.commit()
    await db.refresh(rec)
    return rec


async def delete_scheme(db: AsyncSession, actor, rec: RollNumberScheme) -> None:
    await record_audit(
        db, actor_id=actor.id, actor_role=actor.role,
        action="roll_scheme.delete", resource_type="roll_number_scheme", resource_id=rec.id,
    )
    await db.delete(rec)
    await db.commit()
