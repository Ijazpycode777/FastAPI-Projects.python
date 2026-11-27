"""Study materials. File bytes persist in the database (``file_data`` BYTEA);
metadata mirrors the row.

A material is scoped to a single class — a ClassLevel row already encodes the
(program, part) pair (e.g. "ICS Part 1" is a distinct row from "Medical Part
1"). Student visibility filters by ``class_id``, so a PDF uploaded for ICS
Part 1 is never shown to Medical students or to "Part 1" of any other program.
Subject and section were removed: the upload collects only title, description,
program (used to filter the class list), class and the file.

The file bytes live in ``file_data`` (deferred so list queries never load every
file's bytes). ``storage_key``/``storage_backend`` are retained for backward
compatibility with rows created before this column existed (their bytes are in
local/S3 storage and ``file_data`` is NULL); the download path falls back to
the storage backend for those rows. Deleting a material (teacher/admin) nulls
``file_data`` so the bytes are freed while the audit row remains.
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, LargeBinary, String, text
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
    # File bytes persisted in the database. Deferred so ``select(StudyMaterial)``
    # (the list endpoint) never loads every file's bytes — only the download
    # path explicitly undefer()s this column for the one row it needs. NULL for
    # rows created before this column (their bytes are in local/S3 storage).
    file_data: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True, nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"), nullable=False)

    class_level = relationship("ClassLevel")
