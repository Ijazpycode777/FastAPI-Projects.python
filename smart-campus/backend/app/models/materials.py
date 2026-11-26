"""Study materials. File bytes live in object/local storage; only metadata is persisted.

A material is scoped to a single class — a ClassLevel row already encodes the
(program, part) pair (e.g. "ICS Part 1" is a distinct row from "Medical Part
1"). Student visibility filters by ``class_id``, so a PDF uploaded for ICS
Part 1 is never shown to Medical students or to "Part 1" of any other program.
Subject and section were removed: the upload collects only title, description,
program (used to filter the class list), class and the file.
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPK


class StudyMaterial(UUIDPK, TimestampMixin, Base):
    __tablename__ = "study_materials"
    __table_args__ = (
        Index("ix_material_class", "class_id"),
    )

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    class_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("class_levels.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    storage_backend: Mapped[str] = mapped_column(String(16), nullable=False, default="local", server_default="local")
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)

    class_level = relationship("ClassLevel")
