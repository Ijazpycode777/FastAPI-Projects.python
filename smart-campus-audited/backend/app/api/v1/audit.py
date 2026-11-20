"""Audit log routes (admin)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut
from app.schemas.common import Page, paginate
from app.security.dependencies import require_admin

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=Page[AuditLogOut])
async def list_audit(
    action: str | None = Query(None),
    resource_type: str | None = Query(None),
    actor_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    total = (await db.execute(select(__import__("sqlalchemy").func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return paginate([AuditLogOut.model_validate(r) for r in rows], page, page_size, int(total or 0))
