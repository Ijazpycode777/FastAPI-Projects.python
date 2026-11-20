"""Notices (published announcements) and per-user notifications."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK
from app.utils.helpers import sql_in

AUDIENCES = ("all", "admins", "teachers", "students", "program", "class", "section")


class Notice(UUIDPK, TimestampMixin, Base):
    __tablename__ = "notices"
    __table_args__ = (
        CheckConstraint(
            f"target_audience IN {sql_in(AUDIENCES)}",
            name="notice_audience_check",
        ),
        Index("ix_notice_target", "target_audience"),
        Index("ix_notice_published", "published_at"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    published_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_audience: Mapped[str] = mapped_column(String(16), nullable=False, default="all")
    program_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("programs.id", ondelete="SET NULL"), nullable=True
    )
    class_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="SET NULL"), nullable=True
    )
    section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    publisher = relationship("User")


class Notification(UUIDPK, TimestampMixin, Base):
    """Per-user in-app notification. Delivered only to authorized users."""
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notification_user_unread", "user_id", "read_at"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)  # notice | result | material | fee
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_resource_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    related_resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
