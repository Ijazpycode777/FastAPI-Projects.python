"""Audit log schemas."""
from __future__ import annotations

from datetime import datetime

from app.schemas.common import ORMBase


class AuditLogOut(ORMBase):
    id: str
    actor_id: str | None = None
    actor_role: str | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    before: str | None = None
    after: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    created_at: datetime
