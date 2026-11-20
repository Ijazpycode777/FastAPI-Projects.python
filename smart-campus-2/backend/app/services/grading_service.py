"""Grading policy service: create, validate boundaries, version, activate."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.models.examinations import GradingBoundary, GradingPolicy
from app.repositories.audit import record_audit
from app.services.grading import Boundary, GradingError, next_version, validate_boundaries


async def create_policy(db: AsyncSession, actor, name: str, description: str | None, raw: list[dict]) -> GradingPolicy:
    boundaries = [
        Boundary(b["grade_name"], float(b["min_percentage"]), float(b["max_percentage"]),
                 bool(b.get("is_pass", True)), b.get("description"))
        for b in raw
    ]
    try:
        validate_boundaries(boundaries)
    except GradingError as exc:
        raise ValidationError(str(exc))

    versions = (await db.execute(
        select(GradingPolicy.version).where(GradingPolicy.name == name)
    )).scalars().all()
    version = next_version(list(versions))

    policy = GradingPolicy(name=name, version=version, is_active=False, description=description)
    db.add(policy)
    await db.flush()
    for b in boundaries:
        db.add(GradingBoundary(
            policy_id=policy.id, grade_name=b.grade_name,
            min_percentage=b.min_percentage, max_percentage=b.max_percentage,
            is_pass=b.is_pass, description=b.description,
        ))
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="grading_policy.create", resource_type="grading_policy",
                       resource_id=policy.id, after={"name": name, "version": version})
    await db.commit()
    await db.refresh(policy)
    return policy


async def activate(db: AsyncSession, actor, policy: GradingPolicy) -> GradingPolicy:
    """Activate one policy; deactivate all others. Historical results keep their version."""
    await db.execute(
        update(GradingPolicy).where(GradingPolicy.is_active.is_(True)).values(is_active=False)
    )
    policy.is_active = True
    await record_audit(db, actor_id=actor.id, actor_role=actor.role,
                       action="grading_policy.activate", resource_type="grading_policy", resource_id=policy.id)
    await db.commit()
    await db.refresh(policy)
    return policy


async def active_policy(db: AsyncSession) -> GradingPolicy | None:
    result = await db.execute(select(GradingPolicy).where(GradingPolicy.is_active.is_(True)))
    return result.scalar_one_or_none()
