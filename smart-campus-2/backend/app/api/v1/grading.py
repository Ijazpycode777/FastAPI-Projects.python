"""Grading policy routes (admin)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.database.session import get_db
from app.models.examinations import GradingPolicy
from app.models.user import User
from app.schemas.examinations import GradingPolicyIn, GradingPolicyOut
from app.security.dependencies import get_current_user, require_admin
from app.services import grading_service

router = APIRouter(prefix="/grading", tags=["grading"])


@router.get("", response_model=list[GradingPolicyOut], dependencies=[Depends(get_current_user)])
async def list_policies(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(select(GradingPolicy).order_by(GradingPolicy.name, GradingPolicy.version))
    return [GradingPolicyOut.model_validate(r) for r in rows.scalars().all()]


@router.get("/active", response_model=GradingPolicyOut | None, dependencies=[Depends(get_current_user)])
async def active(db: AsyncSession = Depends(get_db)):
    p = await grading_service.active_policy(db)
    return GradingPolicyOut.model_validate(p) if p else None


@router.post("", response_model=GradingPolicyOut, dependencies=[Depends(require_admin())])
async def create_policy(payload: GradingPolicyIn, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    policy = await grading_service.create_policy(db, admin, payload.name, payload.description,
                                                 [b.model_dump() for b in payload.boundaries])
    return GradingPolicyOut.model_validate(policy)


@router.post("/{policy_id}/activate", response_model=GradingPolicyOut, dependencies=[Depends(require_admin())])
async def activate(policy_id: str, admin: User = Depends(require_admin()), db: AsyncSession = Depends(get_db)):
    policy = await db.get(GradingPolicy, policy_id)
    if policy is None:
        raise NotFoundError("Grading policy not found.")
    return GradingPolicyOut.model_validate(await grading_service.activate(db, admin, policy))
