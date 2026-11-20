"""Server-side session records. The cookie token is opaque; the row is the truth."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK
from app.models.user import User


class Session(UUIDPK, TimestampMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_token", "token", unique=True),
        Index("ix_sessions_user_active", "user_id", "revoked"),
        Index("ix_sessions_expires", "expires_at"),
    )

    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="sessions")

    def is_expired(self) -> bool:
        if self.expires_at.tzinfo is None:
            return self.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
        return self.expires_at <= datetime.now(timezone.utc)
