"""User account model. The single source of truth for identity & role."""
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK


class User(UUIDPK, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin','teacher','student')", name="users_role_check"
        ),
        CheckConstraint("email = lower(email)", name="users_email_lower_check"),
        # Email uniqueness is enforced by this single named unique index
        # (D12: the redundant column-level unique=True was removed so there is
        # exactly one uniqueness mechanism, avoiding a duplicate constraint).
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_role", "role"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False)
    must_reset_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0", nullable=False)
    # D7: stored as timezone-aware timestamps (was String(40)) so range queries,
    # sorting and timezone handling are native and indexable.
    last_login_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, server_default="0", nullable=False)
    locked_until: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    teacher_profile = relationship("Teacher", back_populates="user", uselist=False, lazy="selectin")
    student_profile = relationship("Student", back_populates="user", uselist=False, lazy="selectin")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"

    @property
    def is_student(self) -> bool:
        return self.role == "student"
