"""Session-wide roll uniqueness + one-enrolment-per-session + one-to-one history.

Revision ID: 0008_roll_session_unique
Revises: 0007_material_no_subject_section
Create Date: 2026-11-23

Three coordinated data-integrity changes required by the Smart Campus spec:

1. Roll numbers are unique across the ENTIRE academic session, not per section:
   ``UNIQUE(academic_session_id, section_id, roll_number)`` is replaced by
   ``UNIQUE(academic_session_id, roll_number)``. The same roll may be reused in
   a different session.

2. A student has at most one enrolment per academic session:
   ``UNIQUE(student_id, academic_session_id)``.

3. ``student_academic_history.enrolment_id`` is unique (the relationship is
   already declared one-to-one): ``UNIQUE(enrolment_id)``.

DATA-PRESERVATION POLICY (this migration never deletes or silently rewrites
existing student data):

* Existing student enrolments and academic-history records are NEVER deleted.
* Manually-assigned roll numbers are NEVER silently renumbered.
* Before adding any constraint, the migration VALIDATES the existing data. If
  any rows would violate a new constraint (a student with several enrolments in
  one session; the same roll number used by two enrolments in one session; or
  two history rows for one enrolment), the migration STOPS with a clear report
  that identifies every conflicting record (table, ids, session, roll). No data
  is modified. An administrator resolves the listed conflicts manually (e.g. by
  moving a misplaced enrolment to the correct session, or reassigning a
  duplicate roll), then re-runs ``alembic upgrade head``.
* There is no safe automatic reconciliation for these conflicts: keeping both
  rows would violate the new constraint, and choosing which row to keep would
  silently discard historical enrolments or manually-assigned rolls. So the
  migration refuses rather than guess.

Only when the data is clean does the migration drop the obsolete
``uq_enrolment_session_section_roll`` constraint (and the now-redundant
``ix_enrolment_student_session`` index) and add the three new constraints.

Fully idempotent and guarded (every op checks ``sa.inspect`` first), so it
applies cleanly to:
  * a fresh database — 0001's ``create_all`` already built the new-model
    constraints, so 0008 validates zero rows and skips every constraint op; and
  * an existing database at 0007 — old constraints are present; if the data is
    clean they are swapped for the new ones; if not, the migration aborts with a
    report and leaves everything untouched.

Downgrade is not supported: it would remove constraints the application depends
on.
"""
from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op

revision = "0008_roll_session_unique"
down_revision = "0007_material_no_subject_section"
branch_labels = None
depends_on = None

log = logging.getLogger("smartcampus.migration.0008")


def _has_table(inspector, name: str) -> bool:
    try:
        return inspector.has_table(name)
    except Exception:
        return name in inspector.get_table_names()


def _has_uq(inspector, table: str, name: str) -> bool:
    try:
        return name in {u["name"] for u in inspector.get_unique_constraints(table)}
    except Exception:
        return False


def _has_index(inspector, table: str, name: str) -> bool:
    try:
        return name in {i["name"] for i in inspector.get_indexes(table)}
    except Exception:
        return False


def _validate_data(bind) -> list[str]:
    """Return a list of human-readable conflict descriptions. Empty list means
    the existing data satisfies all three new constraints and the migration may
    proceed. Uses portable SQL (no GROUP_CONCAT/STRING_AGG) so it runs on both
    SQLite and PostgreSQL."""
    conflicts: list[str] = []

    # 1. Duplicate (student_id, academic_session_id): a student with several
    #    enrolments in one session. There is no safe automatic reconciliation
    #    (keeping both rows violates the new constraint), so this is fatal.
    ss_keys = bind.execute(sa.text(
        "SELECT student_id, academic_session_id, COUNT(*) AS n "
        "FROM student_enrolments "
        "GROUP BY student_id, academic_session_id "
        "HAVING COUNT(*) > 1"
    )).all()
    for student_id, session_id, n in ss_keys:
        ids = [r[0] for r in bind.execute(sa.text(
            "SELECT id FROM student_enrolments "
            "WHERE student_id = :st AND academic_session_id = :se "
            "ORDER BY id"
        ), {"st": student_id, "se": session_id}).all()]
        conflicts.append(
            f"student_enrolments: student {student_id} has {n} enrolments in "
            f"academic_session {session_id} (enrolment ids {ids}); at most one "
            f"enrolment per (student, academic_session) is allowed."
        )

    # 2. Duplicate (academic_session_id, roll_number): the same roll number used
    #    by two enrolments in one session (e.g. in different sections, classes
    #    or programs). Roll numbers are manually assigned; we never renumber
    #    them silently, so this is fatal.
    roll_keys = bind.execute(sa.text(
        "SELECT academic_session_id, roll_number, COUNT(*) AS n "
        "FROM student_enrolments "
        "GROUP BY academic_session_id, roll_number "
        "HAVING COUNT(*) > 1"
    )).all()
    for session_id, roll, n in roll_keys:
        ids = [r[0] for r in bind.execute(sa.text(
            "SELECT id FROM student_enrolments "
            "WHERE academic_session_id = :s AND roll_number = :r "
            "ORDER BY id"
        ), {"s": session_id, "r": roll}).all()]
        conflicts.append(
            f"student_enrolments: roll number {roll} is used by {n} enrolments "
            f"in academic_session {session_id} (enrolment ids {ids}); roll "
            f"numbers must be unique across the entire session."
        )

    # 3. Duplicate enrolment_id in student_academic_history: two history
    #    snapshots for one enrolment. The one-to-one relationship allows one.
    if _has_table(sa.inspect(bind), "student_academic_history"):
        hist_keys = bind.execute(sa.text(
            "SELECT enrolment_id, COUNT(*) AS n "
            "FROM student_academic_history "
            "GROUP BY enrolment_id "
            "HAVING COUNT(*) > 1"
        )).all()
        for eid, n in hist_keys:
            ids = [r[0] for r in bind.execute(sa.text(
                "SELECT id FROM student_academic_history "
                "WHERE enrolment_id = :eid ORDER BY id"
            ), {"eid": eid}).all()]
            conflicts.append(
                f"student_academic_history: enrolment {eid} has {n} history rows "
                f"(history ids {ids}); at most one history row per enrolment is "
                f"allowed (one-to-one)."
            )

    return conflicts


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "student_enrolments"):
        return

    # ---- 1. VALIDATE existing data before touching any constraints. ----
    conflicts = _validate_data(bind)
    if conflicts:
        report = "\n".join(f"  - {c}" for c in conflicts)
        log.error("0008: migration ABORTED — %d unresolved data conflict(s):\n%s",
                  len(conflicts), report)
        raise RuntimeError(
            "Migration 0008_roll_session_unique aborted: "
            f"{len(conflicts)} data conflict(s) prevent adding the new unique "
            "constraints. NO data was modified — no enrolment or academic-history "
            "row was deleted and no roll number was changed. Resolve the "
            "conflicts listed below manually (move a misplaced enrolment to the "
            "correct session, reassign a duplicate roll, or remove a duplicate "
            "history row), then re-run `alembic upgrade head`.\n\nConflicts:\n"
            f"{report}"
        )

    # ---- 2. Data is clean: apply the constraints. No rows are modified. ----
    # Drop the obsolete (session, section, roll) unique — superseded by the
    # session-wide (session, roll) unique. Drop the now-redundant (student,
    # session) index — the new UNIQUE(student_id, academic_session_id) creates
    # its own index.
    if _has_uq(inspector, "student_enrolments", "uq_enrolment_session_section_roll"):
        with op.batch_alter_table("student_enrolments") as b:
            b.drop_constraint("uq_enrolment_session_section_roll", type_="unique")
    if _has_index(inspector, "student_enrolments", "ix_enrolment_student_session"):
        with op.batch_alter_table("student_enrolments") as b:
            b.drop_index("ix_enrolment_student_session")

    # Add the new authoritative constraints (guarded — already present on a
    # fresh database built by 0001's create_all with the current models).
    inspector = sa.inspect(bind)
    if not _has_uq(inspector, "student_enrolments", "uq_enrolment_session_roll"):
        with op.batch_alter_table("student_enrolments") as b:
            b.create_unique_constraint(
                "uq_enrolment_session_roll",
                ["academic_session_id", "roll_number"],
            )
    if not _has_uq(inspector, "student_enrolments", "uq_enrolment_student_session"):
        with op.batch_alter_table("student_enrolments") as b:
            b.create_unique_constraint(
                "uq_enrolment_student_session",
                ["student_id", "academic_session_id"],
            )
    if (_has_table(inspector, "student_academic_history")
            and not _has_uq(inspector, "student_academic_history", "uq_academic_history_enrolment")):
        with op.batch_alter_table("student_academic_history") as b:
            b.create_unique_constraint(
                "uq_academic_history_enrolment",
                ["enrolment_id"],
            )
    log.info("0008: data validated clean; new unique constraints applied.")


def downgrade():
    raise NotImplementedError(
        "Downgrade from 0008_roll_session_unique is not supported: it would "
        "remove roll-uniqueness and one-enrolment-per-session constraints the "
        "application depends on."
    )
