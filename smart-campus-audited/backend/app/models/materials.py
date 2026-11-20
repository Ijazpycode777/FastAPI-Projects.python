"""Study materials. File bytes live in object/local storage; only metadata is persisted."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK


class StudyMaterial(UUIDPK, TimestampMixin, Base):
    __tablename__ = "study_materials"
    __table_args__ = (
        Index("ix_material_subject_class", "subject_id", "class_id", "section_id"),
    )

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    subject_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="RESTRICT"), nullable=False
    )
    section_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    storage_backend: Mapped[str] = mapped_column(String(16), nullable=False, default="local")
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    subject = relationship("Subject")
    class_level = relationship("ClassLevel")
