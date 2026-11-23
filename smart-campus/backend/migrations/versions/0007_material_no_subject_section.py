"""drop study_materials subject_id + section_id

Revision ID: 0007_material_no_subject_section
Revises: 0006_departments_subject
Create Date: 2026-11-23

Removes subject and section from study materials. A material is now scoped to a
single class only (title, description, class_id, file). Student visibility
filters by ``class_id`` — and because each ClassLevel row already encodes
(program, part), a PDF uploaded for "ICS Part 1" is never shown to Medical
students or to "Part 1" of any other program.

Drops:
  * study_materials.subject_id  (NOT NULL FK -> subjects.id, ondelete RESTRICT)
  * study_materials.section_id  (nullable FK -> sections.id, ondelete SET NULL)
  * index ix_material_subject_class (subject_id, class_id, section_id)
Adds:
  * index ix_material_class (class_id) — backs the student visibility query.

Idempotent (every op is guarded by ``sa.inspect``) so it applies cleanly to a
fresh database (create_all already built the new schema — 0007 then only
ensures the class index exists) and to an existing database at 0006 (old schema
with the subject/section columns + composite index present).

Downgrade is best-effort: it restores the two columns (subject_id NOT NULL would
fail without data, so it is restored nullable and logged) and the composite
index, and drops the class index. It cannot reconstruct historical subject /
section values.
"""
from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op

log = logging.getLogger("smartcampus.migration.0007")

revision = "0007_material_no_subject_section"
down_revision = "0006_departments_subject"
branch_labels = None
depends_on = None


def _has_col(inspector, table: str, name: str) -> bool:
    try:
        return name in {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return False


def _has_index(inspector, table: str, name: str) -> bool:
    try:
        return name in {i["name"] for i in inspector.get_indexes(table)}
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop the composite subject/class/section index first — it references
    # columns we are about to remove.
    if _has_index(inspector, "study_materials", "ix_material_subject_class"):
        op.drop_index("ix_material_subject_class", table_name="study_materials")

    with op.batch_alter_table("study_materials") as b:
        # Drop each FK constraint before its column (order matters on PG).
        if _has_col(inspector, "study_materials", "subject_id"):
            b.drop_constraint("study_materials_subject_id_fkey", type_="foreignkey")
            b.drop_column("subject_id")
        if _has_col(inspector, "study_materials", "section_id"):
            b.drop_constraint("study_materials_section_id_fkey", type_="foreignkey")
            b.drop_column("section_id")

    # Backing index for the student visibility query (filter by class_id).
    if not _has_index(inspector, "study_materials", "ix_material_class"):
        op.create_index("ix_material_class", "study_materials", ["class_id"])


def downgrade() -> None:
    """Best-effort reverse — see module docstring."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_index(inspector, "study_materials", "ix_material_class"):
        op.drop_index("ix_material_class", table_name="study_materials")

    with op.batch_alter_table("study_materials") as b:
        if not _has_col(inspector, "study_materials", "section_id"):
            b.add_column(sa.Column("section_id", sa.String(length=36), nullable=True))
            b.create_foreign_key(
                "study_materials_section_id_fkey", "sections",
                ["section_id"], ["id"], ondelete="SET NULL",
            )
        # subject_id is restored nullable (historical values are gone); an admin
        # must backfill before re-applying a NOT NULL constraint.
        if not _has_col(inspector, "study_materials", "subject_id"):
            b.add_column(sa.Column("subject_id", sa.String(length=36), nullable=True))
            b.create_foreign_key(
                "study_materials_subject_id_fkey", "subjects",
                ["subject_id"], ["id"], ondelete="RESTRICT",
            )
            log.warning(
                "study_materials.subject_id restored as NULLABLE on downgrade — "
                "backfill before re-applying NOT NULL."
            )

    if not _has_index(inspector, "study_materials", "ix_material_subject_class"):
        op.create_index(
            "ix_material_subject_class", "study_materials",
            ["subject_id", "class_id", "section_id"],
        )
