"""departments, teacher subject, drop classroom

Revision ID: 0006_departments_subject
Revises: 0005_enrolment_roll_integrity
Create Date: 2026-11-21

Implements three coordinated changes required by the Smart Campus spec:

1. Five fixed teacher departments (Literature, Computer Science, Biology,
   Mathematics/Statistics, Physical Sciences) — created as a ``departments``
   table seeded with five rows that carry fixed, reproducible UUIDs. Every
   teacher references exactly one via ``department_id`` (NOT NULL FK).

2. A manually-entered teacher ``subject`` (free text, NOT NULL). Existing
   teacher rows that pre-date this column are backfilled with the explicit
   placeholder ``"Unspecified"`` and the affected rows are logged so an
   administrator can review them — values are never silently invented.

3. Removal of the classroom feature: the ``classrooms`` table, the
   ``timetable_entries.classroom_id`` column + its ``ix_entry_room_day`` index
   + FK. Timetable functionality itself is otherwise untouched.

The migration is fully idempotent (every op is guarded by ``sa.inspect``) so
it applies cleanly to:
  * a fresh database (0001's create_all already built the new schema — 0006
    then only seeds the five department rows), and
  * an existing database at 0005 (old schema with the text ``department``
    column, no ``subject``, classroom table/columns present).

Downgrade is best-effort and documented below — it restores the classroom
objects and the text ``department`` column (left NULL) and drops the new
columns/tables. It does NOT reconstruct historical subject values, since none
existed before this migration.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

log = logging.getLogger("smartcampus.migration.0006")

revision = "0006_departments_subject"
down_revision = "0005_enrolment_roll_integrity"
branch_labels = None
depends_on = None


# ---- five fixed departments (reproducible UUIDs) ----
LITERATURE_ID = "11111111-1111-1111-1111-111111111111"
CS_ID = "22222222-2222-2222-2222-222222222222"
BIOLOGY_ID = "33333333-3333-3333-3333-333333333333"
MATH_ID = "44444444-4444-4444-4444-444444444444"
PHYSICAL_ID = "55555555-5555-5555-5555-555555555555"

# (id, name) — order is the canonical display/sort order in the UI dropdown.
DEPARTMENTS = [
    (LITERATURE_ID, "Literature"),
    (CS_ID, "Computer Science"),
    (BIOLOGY_ID, "Biology"),
    (MATH_ID, "Mathematics/Statistics"),
    (PHYSICAL_ID, "Physical Sciences"),
]

# Fixed placeholder for existing teachers that pre-date the ``subject`` column.
# Clearly marked + logged so an admin reviews; never a fabricated real value.
SUBJECT_PLACEHOLDER = "Unspecified"


# ---- inspector guards (same pattern as 0003/0004) ----
def _has_table(inspector, name: str) -> bool:
    try:
        return inspector.has_table(name)
    except Exception:
        return name in inspector.get_table_names()


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


# Map an existing free-text ``department`` value to one of the five fixed ids.
# Matching is case-insensitive on a prefix/keyword basis; anything unmatched
# (or NULL) falls back to Computer Science — the most generic department — and
# every fallback is logged so nothing is silently reassigned.
_DEPT_CASE = (
    "CASE"
    " WHEN lower(department) = 'literature' THEN :lit"
    " WHEN lower(department) LIKE 'computer%' THEN :cs"
    " WHEN lower(department) = 'biology' THEN :bio"
    " WHEN lower(department) LIKE 'math%' OR lower(department) LIKE 'stat%' THEN :math"
    " WHEN lower(department) LIKE 'phys%' THEN :physical"
    " ELSE :cs"
    " END"
)
_DEPT_PARAMS = {
    "lit": LITERATURE_ID, "cs": CS_ID, "bio": BIOLOGY_ID,
    "math": MATH_ID, "physical": PHYSICAL_ID,
}
_KNOWN_NAMES = {name.lower() for _, name in DEPARTMENTS}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    now = datetime.now(timezone.utc)

    # ---------- 1. departments table + five fixed rows ----------
    if not _has_table(inspector, "departments"):
        op.create_table(
            "departments",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("name", name="uq_departments_name"),
        )

    # Seed any missing department rows (idempotent — safe on fresh + existing).
    for did, dname in DEPARTMENTS:
        exists = bind.execute(
            sa.text("SELECT 1 FROM departments WHERE id = :id"), {"id": did}
        ).scalar()
        if not exists:
            bind.execute(
                sa.text(
                    "INSERT INTO departments (id, name, created_at, updated_at) "
                    "VALUES (:id, :name, :ca, :ua)"
                ),
                {"id": did, "name": dname, "ca": now, "ua": now},
            )

    # ---------- 2. teacher.department_id + teacher.subject ----------
    if _has_table(inspector, "teachers"):
        need_dept = not _has_col(inspector, "teachers", "department_id")
        need_subject = not _has_col(inspector, "teachers", "subject")
        if need_dept or need_subject:
            with op.batch_alter_table("teachers") as b:
                if need_dept:
                    b.add_column(sa.Column("department_id", sa.String(length=36), nullable=True))
                    b.create_foreign_key(
                        "teachers_department_id_fkey", "departments",
                        ["department_id"], ["id"], ondelete="RESTRICT",
                    )
                if need_subject:
                    b.add_column(sa.Column(
                        "subject", sa.String(length=120), nullable=True,
                        server_default=SUBJECT_PLACEHOLDER,
                    ))

        # Backfill department_id from the legacy text column, if it is present.
        if _has_col(inspector, "teachers", "department"):
            bind.execute(
                sa.text(f"UPDATE teachers SET department_id = {_DEPT_CASE} "
                        "WHERE department_id IS NULL"),
                _DEPT_PARAMS,
            )
            # Report any teacher whose department did not match a known name
            # (and was therefore assigned the Computer Science fallback) so the
            # administrator can review — never silently reassigned.
            unmatched = bind.execute(sa.text(
                "SELECT id, email, department FROM teachers "
                "WHERE lower(department) NOT IN :known "
                "AND department IS NOT NULL "
                "AND department <> ''"
            ).bindparams(sa.bindparam("known", expanding=True)), {"known": list(_KNOWN_NAMES)}).all()
            if unmatched:
                log.warning(
                    "0006: %d teacher row(s) had a department that did not match "
                    "the five fixed names and were assigned the 'Computer Science' "
                    "fallback — review: %s",
                    len(unmatched),
                    [(str(r[0]), r[1], r[2]) for r in unmatched],
                )

        # Backfill subject for any NULL row (existing rows predating the column).
        bind.execute(
            sa.text(f"UPDATE teachers SET subject = :ph WHERE subject IS NULL"),
            {"ph": SUBJECT_PLACEHOLDER},
        )
        # Report teachers left on the placeholder so an admin can fill real values.
        placeholder_rows = bind.execute(sa.text(
            "SELECT id, email FROM teachers WHERE subject = :ph"
        ), {"ph": SUBJECT_PLACEHOLDER}).all()
        if placeholder_rows:
            log.warning(
                "0006: %d teacher row(s) have the 'Unspecified' subject placeholder "
                "— an administrator should set a real subject via the edit form: %s",
                len(placeholder_rows),
                [(str(r[0]), r[1]) for r in placeholder_rows],
            )

        # Tighten to NOT NULL + drop the legacy text department column.
        with op.batch_alter_table("teachers") as b:
            b.alter_column("department_id", existing_type=sa.String(length=36), nullable=False)
            b.alter_column("subject", existing_type=sa.String(length=120), nullable=False)
            if _has_col(inspector, "teachers", "department"):
                b.drop_column("department")

    # ---------- 3. drop classroom from timetable_entries ----------
    if _has_table(inspector, "timetable_entries") and _has_col(inspector, "timetable_entries", "classroom_id"):
        if _has_index(inspector, "timetable_entries", "ix_entry_room_day"):
            op.drop_index("ix_entry_room_day", table_name="timetable_entries")
        with op.batch_alter_table("timetable_entries") as b:
            b.drop_column("classroom_id")

    # ---------- 4. drop the classrooms table ----------
    if _has_table(inspector, "classrooms"):
        op.drop_table("classrooms")


def downgrade() -> None:
    """Best-effort reverse.

    Restores the classroom objects (table + timetable_entries.classroom_id +
    ix_entry_room_day) and the legacy text ``teachers.department`` column
    (left NULL — historical text values are not reconstructible). Drops the new
    ``teachers.department_id`` (FK) + ``teachers.subject`` columns and the
    ``departments`` table.

    NOTE: subject values are NOT restored (none existed before 0006). Run only
    on an empty/development database; never against production without a backup.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 4. classrooms table
    if not _has_table(inspector, "classrooms"):
        op.create_table(
            "classrooms",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("room_number", sa.String(length=24), nullable=False),
            sa.Column("building", sa.String(length=80), nullable=True),
            sa.Column("capacity", sa.Integer(), nullable=False, server_default="40"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("room_number", name="uq_classrooms_room_number"),
        )

    # 3. timetable_entries.classroom_id + index
    if _has_table(inspector, "timetable_entries") and not _has_col(inspector, "timetable_entries", "classroom_id"):
        with op.batch_alter_table("timetable_entries") as b:
            b.add_column(sa.Column(
                "classroom_id", sa.String(length=36),
                sa.ForeignKey("classrooms.id", ondelete="SET NULL"), nullable=True,
            ))
        if not _has_index(inspector, "timetable_entries", "ix_entry_room_day"):
            op.create_index("ix_entry_room_day", "timetable_entries", ["classroom_id", "day_of_week"])

    # 2. teacher: restore text department, drop department_id + subject
    if _has_table(inspector, "teachers"):
        if not _has_col(inspector, "teachers", "department"):
            with op.batch_alter_table("teachers") as b:
                b.add_column(sa.Column("department", sa.String(length=80), nullable=True))
        if _has_col(inspector, "teachers", "department_id"):
            with op.batch_alter_table("teachers") as b:
                b.drop_constraint("teachers_department_id_fkey", type_="foreignkey")
                b.drop_column("department_id")
        if _has_col(inspector, "teachers", "subject"):
            with op.batch_alter_table("teachers") as b:
                b.drop_column("subject")

    # 1. departments table
    if _has_table(inspector, "departments"):
        op.drop_table("departments")
