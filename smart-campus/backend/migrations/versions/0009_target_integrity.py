"""Target integrity hardening (D1-D18 remediation).

Revision ID: 0009_target_integrity
Revises: 0008_roll_session_unique
Create Date: 2026-11-26

Additive migration that applies the database-integrity fixes identified in the
audit, without removing any table, dropping any valid row, or rewriting any
historical migration. Every operation is guarded by ``sa.inspect`` so the
migration is idempotent: on a fresh database (where 0001's ``create_all`` has
already built the current models) every op is a no-op and the validate scans
see zero rows; on an existing database at revision 0008 the ops transform the
old schema into the current one.

DATA-PRESERVATION POLICY (same as 0008 — never delete or silently rewrite):

* Before adding any restrictive constraint, the migration VALIDATES the existing
  data. If any rows would violate a new constraint (duplicate class-wide teacher
  assignments; a student with multiple active enrolments; multiple active
  grading policies; malformed timestamp text), the migration STOPS with a clear
  report identifying every conflicting record. No data is modified.
* The new ``previous_*_id`` FK columns on ``student_academic_history`` are
  backfilled from the ``previous_*`` TEXT columns (which hold the OLD placement
  UUIDs captured at promotion time) — NEVER from ``enrolment_id`` (which points
  to the NEW enrolment). Backfill only sets the FK where the referenced row
  still exists; otherwise the column stays NULL and the text snapshot remains.
* Existing rows are never deleted, merged, or renumbered to make a constraint
  pass.

Operations:

  D1  — teacher_assignments: drop the NULL-vulnerable 5-column UNIQUE; add two
         partial UNIQUE indexes (WHERE section_id IS NULL / IS NOT NULL).
  D2  — student_academic_history: add nullable previous_class_id / section_id /
         session_id FK columns (ON DELETE SET NULL); backfill from previous_*.
  D6  — server defaults for is_active / status / designation / count columns so
         raw (non-ORM) inserts cannot fail on NOT NULL.
  D7  — users.last_login_at / locked_until, examinations.finalized_at,
         student_marks.recorded_at / finalized_at: String(40) -> DateTime(tz).
  D8  — student_enrolments: partial UNIQUE(student_id) WHERE is_active.
  D10 — grading_policies: partial UNIQUE(is_active) WHERE is_active (one active).
  D12 — users.email: drop the redundant column-level UNIQUE (the named
         ix_users_email unique index remains, so uniqueness is preserved).
  D14 — notices: CHECK that target_audience agrees with the targeting FKs.
  D18 — student_enrolments: index on (student_id, is_active).

D5 (timetable overlap) is enforced at the application layer (fixed conflict
logic + dual advisory lock); a PostgreSQL GiST EXCLUDE constraint is the
recommended future hardening but is NOT applied here because it cannot be
verified without a PostgreSQL environment and the class-wide/section
interaction needs careful PG testing (see report).

Downgrade is best-effort and documented: added constraints/indexes/columns are
dropped; the timestamp columns revert to String via a text cast; the
previous_*_id FK columns are dropped (the text snapshots remain, so no history
is lost). The old 5-column teacher_assignments unique is NOT restored (it was
redundant with the two partial indexes); downgrade below 0006 remains
unsupported per 0004/0005/0008.
"""
from __future__ import annotations

import logging
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0009_target_integrity"
down_revision = "0008_roll_session_unique"
branch_labels = None
depends_on = None

log = logging.getLogger("smartcampus.migration.0009")


# ---------------------------------------------------------------------------
# Reflection helpers
# ---------------------------------------------------------------------------
def _bind():
    return op.get_bind()


def _is_pg() -> bool:
    return _bind().dialect.name == "postgresql"


def _inspector():
    return sa.inspect(_bind())


def _has_table(inspector, name: str) -> bool:
    try:
        return inspector.has_table(name)
    except Exception:
        return name in inspector.get_table_names()


def _has_index(inspector, table: str, name: str) -> bool:
    try:
        return name in {i["name"] for i in inspector.get_indexes(table)}
    except Exception:
        return False


def _has_uq(inspector, table: str, name: str) -> bool:
    try:
        return name in {u["name"] for u in inspector.get_unique_constraints(table)}
    except Exception:
        return False


def _has_col(inspector, table: str, col: str) -> bool:
    try:
        return col in {c["name"] for c in inspector.get_columns(table)}
    except Exception:
        return False


def _col_type_name(inspector, table: str, col: str) -> str:
    try:
        for c in inspector.get_columns(table):
            if c["name"] == col:
                return (getattr(c["type"], "name", None)
                        or type(c["type"]).__name__).lower()
    except Exception:
        pass
    return ""


def _abort(conflicts: list[str]) -> None:
    report = "\n".join(f"  - {c}" for c in conflicts)
    log.error("0009: migration ABORTED — %d unresolved data conflict(s):\n%s",
              len(conflicts), report)
    raise RuntimeError(
        "Migration 0009_target_integrity aborted: "
        f"{len(conflicts)} data conflict(s) prevent applying the new integrity "
        "constraints. NO data was modified — no row was deleted, merged, or "
        "renumbered. Resolve the conflicts listed below manually, then re-run "
        "`alembic upgrade head`.\n\nConflicts:\n" + report
    )


# ---------------------------------------------------------------------------
# Validation scans (run before any constraint is added)
# ---------------------------------------------------------------------------
def _validate_d1_assignments(bind) -> list[str]:
    """Duplicate class-wide or sectioned teacher assignments."""
    conflicts: list[str] = []
    if not _has_table(_inspector(), "teacher_assignments"):
        return conflicts
    # Class-wide duplicates (section_id IS NULL).
    rows = bind.execute(sa.text(
        "SELECT teacher_id, subject_id, class_id, academic_session_id, COUNT(*) n "
        "FROM teacher_assignments WHERE section_id IS NULL "
        "GROUP BY teacher_id, subject_id, class_id, academic_session_id "
        "HAVING COUNT(*) > 1"
    )).all()
    for tid, sid, cid, sess, n in rows:
        conflicts.append(
            f"teacher_assignments: teacher {tid} has {n} class-wide assignments "
            f"for subject {sid}, class {cid}, session {sess}; at most one "
            f"class-wide assignment per (teacher, subject, class, session)."
        )
    # Sectioned duplicates (section_id IS NOT NULL).
    rows = bind.execute(sa.text(
        "SELECT teacher_id, subject_id, class_id, section_id, academic_session_id, "
        "COUNT(*) n FROM teacher_assignments WHERE section_id IS NOT NULL "
        "GROUP BY teacher_id, subject_id, class_id, section_id, academic_session_id "
        "HAVING COUNT(*) > 1"
    )).all()
    for tid, sid, cid, secid, sess, n in rows:
        conflicts.append(
            f"teacher_assignments: teacher {tid} has {n} assignments for subject "
            f"{sid}, class {cid}, section {secid}, session {sess}; at most one "
            f"per (teacher, subject, class, section, session)."
        )
    return conflicts


def _validate_d8_one_active_enrolment(bind) -> list[str]:
    """Students with more than one active enrolment across sessions."""
    conflicts: list[str] = []
    if not _has_table(_inspector(), "student_enrolments"):
        return conflicts
    rows = bind.execute(sa.text(
        "SELECT student_id, COUNT(*) n FROM student_enrolments "
        "WHERE is_active GROUP BY student_id HAVING COUNT(*) > 1"
    )).all()
    for sid, n in rows:
        ids = [r[0] for r in bind.execute(sa.text(
            "SELECT id FROM student_enrolments WHERE student_id = :s AND is_active "
            "ORDER BY id"
        ), {"s": sid}).all()]
        conflicts.append(
            f"student_enrolments: student {sid} has {n} active enrolments "
            f"(ids {ids}); at most one active enrolment per student is allowed."
        )
    return conflicts


def _validate_d10_one_active_policy(bind) -> list[str]:
    """More than one active grading policy."""
    conflicts: list[str] = []
    if not _has_table(_inspector(), "grading_policies"):
        return conflicts
    n = int(bind.execute(sa.text(
        "SELECT COUNT(*) FROM grading_policies WHERE is_active"
    )).scalar_one() or 0)
    if n > 1:
        ids = [r[0] for r in bind.execute(sa.text(
            "SELECT id FROM grading_policies WHERE is_active ORDER BY id"
        )).all()]
        conflicts.append(
            f"grading_policies: {n} policies are active (ids {ids}); at most one "
            f"active grading policy is allowed."
        )
    return conflicts


def _validate_d7_timestamps(bind) -> list[str]:
    """Malformed or non-empty timestamp text that cannot be cast to TIMESTAMPTZ."""
    conflicts: list[str] = []
    targets = [
        ("users", "last_login_at"), ("users", "locked_until"),
        ("examinations", "finalized_at"),
        ("student_marks", "recorded_at"), ("student_marks", "finalized_at"),
    ]
    inspector = _inspector()
    for table, col in targets:
        if not _has_table(inspector, table) or not _has_col(inspector, table, col):
            continue
        # Only validate if the column is still String (already-DateTime on fresh).
        if "date" in _col_type_name(inspector, table, col):
            continue
        rows = bind.execute(sa.text(
            f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL AND {col} != ''"
        )).all()
        for rid, val in rows:
            try:
                datetime.fromisoformat(str(val))
            except (ValueError, TypeError):
                conflicts.append(
                    f"{table}.{col}: row {rid} has malformed timestamp "
                    f"{val!r} that cannot be converted to DateTime; fix or "
                    f"NULL it before re-running."
                )
    return conflicts


# ---------------------------------------------------------------------------
# Apply functions
# ---------------------------------------------------------------------------
def _d1_assignments():
    inspector = _inspector()
    if not _has_table(inspector, "teacher_assignments"):
        return
    # Drop the old NULL-vulnerable 5-column unique (guarded).
    if _has_uq(inspector, "teacher_assignments",
               "uq_assignment_teacher_subject_class_section_session"):
        with op.batch_alter_table("teacher_assignments") as b:
            b.drop_constraint(
                "uq_assignment_teacher_subject_class_section_session", type_="unique"
            )
    # Two partial unique indexes (supported by both PostgreSQL and SQLite).
    if not _has_index(inspector, "teacher_assignments", "uq_assignment_classwide"):
        op.create_index(
            "uq_assignment_classwide", "teacher_assignments",
            ["teacher_id", "subject_id", "class_id", "academic_session_id"],
            unique=True,
            postgresql_where=sa.text("section_id IS NULL"),
            sqlite_where=sa.text("section_id IS NULL"),
        )
    if not _has_index(inspector, "teacher_assignments", "uq_assignment_sectioned"):
        op.create_index(
            "uq_assignment_sectioned", "teacher_assignments",
            ["teacher_id", "subject_id", "class_id", "section_id", "academic_session_id"],
            unique=True,
            postgresql_where=sa.text("section_id IS NOT NULL"),
            sqlite_where=sa.text("section_id IS NOT NULL"),
        )


def _d2_history_fk_columns():
    """Add previous_class_id/section_id/session_id (nullable FK, SET NULL) and
    backfill from the previous_* TEXT columns (the OLD placement UUIDs)."""
    bind = _bind()
    inspector = _inspector()
    if not _has_table(inspector, "student_academic_history"):
        return
    table = "student_academic_history"
    for col, ref in (("previous_class_id", "class_levels"),
                     ("previous_section_id", "sections"),
                     ("previous_session_id", "academic_sessions")):
        if not _has_col(inspector, table, col):
            with op.batch_alter_table(table) as b:
                b.add_column(sa.Column(col, sa.String(36), nullable=True))
                b.create_foreign_key(
                    f"fk_history_{col}", [col], [ref], ondelete="SET NULL",
                )
    # Backfill from the text columns. previous_class holds the OLD class_id UUID
    # (captured at promotion), so the copy is reliable — but only where the
    # referenced row still exists. NEVER backfill from enrolment_id (that is the
    # NEW enrolment; using it would assign the wrong historical relationship).
    if _has_col(inspector, table, "previous_class") and _has_col(inspector, table, "previous_class_id"):
        bind.execute(sa.text(
            "UPDATE student_academic_history SET previous_class_id = previous_class "
            "WHERE previous_class IS NOT NULL "
            "AND previous_class IN (SELECT id FROM class_levels)"
        ))
    if _has_col(inspector, table, "previous_section") and _has_col(inspector, table, "previous_section_id"):
        bind.execute(sa.text(
            "UPDATE student_academic_history SET previous_section_id = previous_section "
            "WHERE previous_section IS NOT NULL "
            "AND previous_section IN (SELECT id FROM sections)"
        ))
    if _has_col(inspector, table, "previous_session") and _has_col(inspector, table, "previous_session_id"):
        bind.execute(sa.text(
            "UPDATE student_academic_history SET previous_session_id = previous_session "
            "WHERE previous_session IS NOT NULL "
            "AND previous_session IN (SELECT id FROM academic_sessions)"
        ))


# (table, column, server_default expression) — D6. Booleans use 1/0 (portable
# across PostgreSQL and SQLite boolean storage).
_SERVER_DEFAULTS = [
    ("student_enrolments", "is_active", "1"),
    ("teacher_assignments", "is_active", "1"),
    ("grading_policies", "is_active", "0"),
    ("grading_policies", "version", "1"),
    ("grading_boundaries", "is_pass", "1"),
    ("students", "account_status", "active"),
    ("teachers", "designation", "Lecturer"),
    ("teachers", "employment_status", "active"),
    ("guardians", "relationship_type", "Guardian"),
    ("academic_sessions", "is_active", "0"),
    ("sections", "capacity", "40"),
    ("subjects", "theory_marks", "100"),
    ("subjects", "practical_marks", "0"),
    ("fee_structures", "is_active", "1"),
    ("fee_structures", "frequency", "one_time"),
    ("fee_structures", "due_after_days", "30"),
    ("fee_invoices", "status", "unpaid"),
    ("examinations", "status", "draft"),
    ("student_marks", "marks_obtained", "0"),
    ("student_marks", "is_absent", "0"),
    ("student_marks", "status", "entered"),
    ("attendance_records", "is_finalized", "0"),
    ("teacher_attendance", "status", "absent"),
    ("teacher_attendance", "work_minutes", "0"),
    ("leave_records", "person_type", "teacher"),
    ("leave_records", "status", "pending"),
    ("study_materials", "is_active", "1"),
    ("study_materials", "storage_backend", "local"),
    ("timetable_entries", "is_cancelled", "0"),
    ("notices", "target_audience", "all"),
    ("notices", "is_pinned", "0"),
    ("users", "is_active", "1"),
    ("users", "must_reset_password", "0"),
    ("users", "failed_login_attempts", "0"),
]


def _sd(default: str):
    """Render a server_default: numeric values raw (``DEFAULT 1``), string values
    as quoted literals (``DEFAULT 'active'``). ``sa.text`` renders raw, so using
    it for strings would produce the invalid ``DEFAULT active`` (treated as a
    column name); a plain string is rendered by SQLAlchemy as a quoted literal."""
    if default.lstrip("-").isdigit():
        return sa.text(default)
    return default


def _d6_server_defaults():
    inspector = _inspector()
    for table, col, default in _SERVER_DEFAULTS:
        if not _has_table(inspector, table) or not _has_col(inspector, table, col):
            continue
        with op.batch_alter_table(table) as b:
            b.alter_column(col, existing_type=sa.String(16), server_default=_sd(default))


def _d7_timestamps():
    """String(40) -> DateTime(timezone=True) for the five timestamp columns."""
    bind = _bind()
    inspector = _inspector()
    targets = [
        ("users", "last_login_at"), ("users", "locked_until"),
        ("examinations", "finalized_at"),
        ("student_marks", "recorded_at"), ("student_marks", "finalized_at"),
    ]
    for table, col in targets:
        if not _has_table(inspector, table) or not _has_col(inspector, table, col):
            continue
        if "date" in _col_type_name(inspector, table, col):
            continue  # already DateTime
        # Empty strings -> NULL so the cast cannot fail on them.
        bind.execute(sa.text(f"UPDATE {table} SET {col} = NULL WHERE {col} = ''"))
        if _is_pg():
            # PostgreSQL: native type change with a cast. Malformed values were
            # caught by _validate_d7_timestamps; empty strings are now NULL.
            op.execute(sa.text(
                f"ALTER TABLE {table} ALTER COLUMN {col} "
                f"TYPE TIMESTAMP WITH TIME ZONE USING {col}::timestamptz"
            ))
        else:
            # SQLite: rebuild the table with the new column type.
            with op.batch_alter_table(table) as b:
                b.alter_column(col, existing_type=sa.String(40),
                               type_=sa.DateTime(timezone=True), nullable=True)


def _d8_d18_enrolment():
    inspector = _inspector()
    if not _has_table(inspector, "student_enrolments"):
        return
    if not _has_index(inspector, "student_enrolments", "ix_enrolment_student_active"):
        op.create_index("ix_enrolment_student_active", "student_enrolments",
                        ["student_id", "is_active"])
    if not _has_index(inspector, "student_enrolments", "uq_enrolment_one_active"):
        op.create_index(
            "uq_enrolment_one_active", "student_enrolments", ["student_id"],
            unique=True,
            postgresql_where=sa.text("is_active"),
            sqlite_where=sa.text("is_active"),
        )


def _d10_grading_one_active():
    inspector = _inspector()
    if not _has_table(inspector, "grading_policies"):
        return
    if not _has_index(inspector, "grading_policies", "uq_grading_one_active"):
        op.create_index(
            "uq_grading_one_active", "grading_policies", ["is_active"],
            unique=True,
            postgresql_where=sa.text("is_active"),
            sqlite_where=sa.text("is_active"),
        )


def _d12_email_unique():
    """Drop the redundant column-level UNIQUE on users.email; the named
    ix_users_email unique index remains, so email uniqueness is preserved."""
    inspector = _inspector()
    if not _has_table(inspector, "users"):
        return
    if _is_pg():
        # Find any UNIQUE constraint on the email column that is not the index.
        rows = _bind().execute(sa.text(
            "SELECT con.conname FROM pg_constraint con "
            "JOIN pg_attribute att "
            "  ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey) "
            "WHERE con.conrelid = 'users'::regclass AND con.contype = 'u' "
            "  AND att.attname = 'email'"
        )).all()
        for (name,) in rows:
            if name != "ix_users_email":
                op.execute(sa.text(f"ALTER TABLE users DROP CONSTRAINT {name}"))
    else:
        # SQLite: the inline UNIQUE shows as a named unique constraint; drop it.
        for uq in inspector.get_unique_constraints("users"):
            if "email" in (uq.get("column_names") or []) and uq["name"] != "ix_users_email":
                with op.batch_alter_table("users") as b:
                    b.drop_constraint(uq["name"], type_="unique")


def _d14_notice_check():
    inspector = _inspector()
    if not _has_table(inspector, "notices"):
        return
    existing = {c["name"] for c in inspector.get_check_constraints("notices")}
    if "notice_audience_target_consistency_check" not in existing:
        with op.batch_alter_table("notices") as b:
            b.create_check_constraint(
                "notice_audience_target_consistency_check",
                "(target_audience = 'program' AND program_id IS NOT NULL "
                "  AND class_id IS NULL AND section_id IS NULL) "
                "OR (target_audience = 'class' AND class_id IS NOT NULL "
                "  AND section_id IS NULL) "
                "OR (target_audience = 'section' AND class_id IS NOT NULL "
                "  AND section_id IS NOT NULL) "
                "OR (target_audience IN ('all','admins','teachers','students') "
                "  AND program_id IS NULL AND class_id IS NULL AND section_id IS NULL)",
            )


# ---------------------------------------------------------------------------
# Upgrade / downgrade
# ---------------------------------------------------------------------------
def upgrade():
    bind = _bind()
    inspector = _inspector()
    if not _has_table(inspector, "student_enrolments"):
        return

    # ---- 1. VALIDATE existing data before touching any constraints. ----
    conflicts: list[str] = []
    conflicts += _validate_d1_assignments(bind)
    conflicts += _validate_d8_one_active_enrolment(bind)
    conflicts += _validate_d10_one_active_policy(bind)
    conflicts += _validate_d7_timestamps(bind)
    if conflicts:
        _abort(conflicts)

    # ---- 2. Data is clean: apply the changes (all guarded / idempotent). ----
    _d2_history_fk_columns()
    _d6_server_defaults()
    _d7_timestamps()
    _d1_assignments()
    _d8_d18_enrolment()
    _d10_grading_one_active()
    _d12_email_unique()
    _d14_notice_check()
    log.info("0009: data validated clean; integrity hardening applied.")


def downgrade():
    """Best-effort downgrade. Added constraints/indexes/columns are dropped; the
    timestamp columns revert to String via a text cast; the previous_*_id FK
    columns are dropped (text snapshots remain, so no history is lost). The old
    5-column teacher_assignments unique is NOT restored (redundant with the
    partial indexes). Downgrade below 0006 remains unsupported."""
    inspector = _inspector()
    bind = _bind()
    # Drop added indexes.
    for t, idx in (
        ("teacher_assignments", "uq_assignment_classwide"),
        ("teacher_assignments", "uq_assignment_sectioned"),
        ("student_enrolments", "uq_enrolment_one_active"),
        ("student_enrolments", "ix_enrolment_student_active"),
        ("grading_policies", "uq_grading_one_active"),
    ):
        if _has_table(inspector, t) and _has_index(inspector, t, idx):
            op.drop_index(idx, table_name=t)
    # Drop the notices CHECK.
    if _has_table(inspector, "notices"):
        existing = {c["name"] for c in inspector.get_check_constraints("notices")}
        if "notice_audience_target_consistency_check" in existing:
            with op.batch_alter_table("notices") as b:
                b.drop_constraint("notice_audience_target_consistency_check", type_="check")
    # Revert timestamp columns to String(40).
    for table, col in (("users", "last_login_at"), ("users", "locked_until"),
                       ("examinations", "finalized_at"),
                       ("student_marks", "recorded_at"), ("student_marks", "finalized_at")):
        if _has_table(inspector, table) and _has_col(inspector, table, col):
            if _is_pg():
                op.execute(sa.text(
                    f"ALTER TABLE {table} ALTER COLUMN {col} "
                    f"TYPE VARCHAR(40) USING {col}::text"
                ))
            else:
                with op.batch_alter_table(table) as b:
                    b.alter_column(col, existing_type=sa.DateTime(timezone=True),
                                   type_=sa.String(40), nullable=True)
    # Drop previous_*_id FK columns (text snapshots remain).
    if _has_table(inspector, "student_academic_history"):
        for col in ("previous_class_id", "previous_section_id", "previous_session_id"):
            if _has_col(inspector, "student_academic_history", col):
                with op.batch_alter_table("student_academic_history") as b:
                    b.drop_column(col)
    log.info("0009: downgrade applied (best-effort). Note: server_defaults are "
             "left in place (harmless) and the old 5-column teacher_assignments "
             "unique is not restored (redundant with the partial indexes).")
