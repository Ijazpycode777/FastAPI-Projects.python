"""Append-only audit log. Records every important state-changing operation."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK


class AuditLog(UUIDPK, TimestampMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_actor", "actor_id"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
        Index("ix_audit_action", "action"),
    )

    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    before: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON snapshot
    after: Mapped[str | None] = mapped_column(Text, nullable=True)    # JSON snapshot
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    actor = relationship("User")
