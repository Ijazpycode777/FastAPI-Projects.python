"""Store study-material file bytes in the database (file_data BYTEA column).

Revision ID: 0010_material_file_data
Revises: 0009_target_integrity
Create Date: 2026-11-27

Additive, safe migration: adds a single nullable ``file_data`` column
(POSTGRES ``BYTEA`` / SQLite ``BLOB``) to ``study_materials``. No existing
column is changed, no row is deleted, no constraint is added.

Rationale: previously file bytes lived only in local/S3 storage and only
metadata was persisted, so an uploaded file could be lost if the storage
volume was recycled. The bytes now persist in the database alongside the
metadata row, so a material is retained exactly as uploaded until a teacher or
admin deletes it. The column is NULL for rows created before this migration
(their bytes remain in local/S3 storage); the download path falls back to the
storage backend for those rows, so existing materials keep working unchanged.

The ORM marks this column ``deferred`` so list queries never load every file's
bytes; the download/preview path explicitly ``undefer()``s it for the one row
it needs. The migration only adds the column; deferral is an ORM-level concern
that does not affect the schema.
"""
from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op

revision = "0010_material_file_data"
down_revision = "0009_target_integrity"
branch_labels = None
depends_on = None

log = logging.getLogger("smartcampus.migration.0010")


def _bind():
    return op.get_bind()


def _inspector():
    return sa.inspect(_bind())


def _has_table(inspector, name: str) -> bool:
    try:
        return inspector.has_table(name)
    except Exception:
        return name in inspector.get_table_names()


def _has_col(inspector, table: str, col: str) -> bool:
    try:
        return col in {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return False


def upgrade():
    inspector = _inspector()
    if not _has_table(inspector, "study_materials"):
        log.info("0010: study_materials table absent — nothing to do (fresh DB).")
        return
    if _has_col(inspector, "study_materials", "file_data"):
        log.info("0010: study_materials.file_data already present — no-op.")
        return
    with op.batch_alter_table("study_materials") as b:
        b.add_column(sa.Column("file_data", sa.LargeBinary, nullable=True))
    log.info("0010: added nullable file_data (BYTEA/BLOB) to study_materials.")


def downgrade():
    inspector = _inspector()
    if _has_table(inspector, "study_materials") and _has_col(inspector, "study_materials", "file_data"):
        with op.batch_alter_table("study_materials") as b:
            b.drop_column("file_data")
        log.info("0010: dropped study_materials.file_data (best-effort downgrade).")
