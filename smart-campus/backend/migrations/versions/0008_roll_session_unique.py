"""Session-wide roll uniqueness + one-enrolment-per-session + one-to-one history.

Revision ID: 0008_roll_session_unique
Revises: 0007_material_no_subject_section
Create Date: 2026-11-23

Three coordinated data-integrity changes required by the Smart Campus spec:

1. Roll numbers are unique across the ENTIRE academic session, not per section.
   ``UNIQUE(academic_session_id, section_id, roll_number)`` is replaced by
   ``UNIQUE(academic_session_id, roll_number)``. Existing duplicate
   (session, roll) rows — possible because rolls used to be scoped per section,
   so the same roll could legitimately appear in different sections of one
   session — are resolved deterministically by renumbering: in each duplicate
   group the earliest row keeps its roll and each later row moves to the
   smallest unused roll in the session. No enrolment is deleted and no student
   loses a roll except a conflicting duplicate.

2. A student has at most one enrolment per academic session:
   ``UNIQUE(student_id, academic_session_id)``. Existing same-session
   duplicates — artifacts of the old promote logic, which created a second
   enrolment row for a same-session section change — are resolved by keeping
   the active / most-recent enrolment and removing the older same-session
   duplicate(s) (and their history rows). Past-session enrolments are NEVER
   touched; only same-session duplicates are removed.

3. ``student_academic_history.enrolment_id`` is unique (the relationship is
   already declared one-to-one). Duplicate history rows per enrolment, if any,
   are resolved by keeping the most recent.

After the renumbering, ``students.current_roll_number`` is re-synced with the
active enrolment's roll. Every data change is logged via the migration logger.

Fully idempotent and guarded (every op checks ``sa.inspect`` first), so it
applies cleanly to:
  * a fresh database — 0001's ``create_all`` already built the new-model
    constraints, so 0008 resolves zero rows and skips every constraint op; and
  * an existing database at 0007 — old constraints are present, duplicates (if
    any) are resolved, old constraints dropped, new constraints added.

Downgrade is not supported: it would remove constraints the application depends
on and undo an irreversible data renumbering / duplicate removal.
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


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "student_enrolments"):
        return

    # ---- 1. Resolve duplicate (student_id, academic_session_id) rows. ----
    # The new UNIQUE(student_id, academic_session_id) forbids two enrolments for
    # the same student in the same session. The old promote logic could create
    # these (a same-session section change deactivated the old enrolment and
    # inserted a new one in the same session). Keep the best row per
    # (student, session) — prefer is_active, then most recent — and remove the
    # older same-session duplicate(s). Past-session enrolments are NEVER touched.
    ss_groups = bind.execute(sa.text(
        "SELECT student_id, academic_session_id FROM student_enrolments "
        "GROUP BY student_id, academic_session_id HAVING COUNT(*) > 1"
    )).all()
    removed_enrolments = 0
    removed_history = 0
    for student_id, session_id in ss_groups:
        rows = bind.execute(sa.text(
            "SELECT id FROM student_enrolments "
            "WHERE student_id = :st AND academic_session_id = :se "
            "ORDER BY is_active DESC, created_at DESC, id"
        ), {"st": student_id, "se": session_id}).all()
        keep_id = rows[0][0]
        for (rid,) in rows[1:]:
            # Remove this enrolment's history rows first (explicit; do not rely
            # on a FK cascade, which SQLite does not enforce without a pragma).
            dh = bind.execute(sa.text(
                "DELETE FROM student_academic_history WHERE enrolment_id = :id"
            ), {"id": rid})
            removed_history += dh.rowcount or 0
            bind.execute(sa.text(
                "DELETE FROM student_enrolments WHERE id = :id"
            ), {"id": rid})
            removed_enrolments += 1
            log.info(
                "0008: removed same-session duplicate enrolment %s "
                "(student %s, session %s); kept enrolment %s",
                rid, student_id, session_id, keep_id,
            )
    log.info(
        "0008: removed %d same-session duplicate enrolment(s) and %d history row(s)",
        removed_enrolments, removed_history,
    )

    # ---- 2. Resolve duplicate enrolment_id in student_academic_history. ----
    # The new UNIQUE(enrolment_id) requires at most one history row per
    # enrolment. Keep the most recent; remove older duplicates.
    if _has_table(inspector, "student_academic_history"):
        hist_groups = bind.execute(sa.text(
            "SELECT enrolment_id FROM student_academic_history "
            "GROUP BY enrolment_id HAVING COUNT(*) > 1"
        )).all()
        removed_hist_dups = 0
        for (eid,) in hist_groups:
            rows = bind.execute(sa.text(
                "SELECT id FROM student_academic_history WHERE enrolment_id = :eid "
                "ORDER BY created_at DESC, id"
            ), {"eid": eid}).all()
            for (hid,) in rows[1:]:
                bind.execute(sa.text(
                    "DELETE FROM student_academic_history WHERE id = :id"
                ), {"id": hid})
                removed_hist_dups += 1
                log.info(
                    "0008: removed duplicate history row %s for enrolment %s", hid, eid)
        log.info("0008: removed %d duplicate history row(s)", removed_hist_dups)

    # ---- 3. Renumber duplicate (academic_session_id, roll_number) rows. ----
    # Rolls are now session-wide unique. Existing duplicates (rolls used to be
    # per-section) are resolved by keeping the earliest row's roll and moving
    # each later row to the smallest unused roll in the session. No enrolment is
    # deleted; no student loses a roll except a conflicting duplicate.
    roll_groups = bind.execute(sa.text(
        "SELECT academic_session_id, roll_number FROM student_enrolments "
        "GROUP BY academic_session_id, roll_number HAVING COUNT(*) > 1"
    )).all()
    renumbered = 0
    for session_id, dup_roll in roll_groups:
        rows = bind.execute(sa.text(
            "SELECT id, student_id FROM student_enrolments "
            "WHERE academic_session_id = :s AND roll_number = :r "
            "ORDER BY created_at, id"
        ), {"s": session_id, "r": dup_roll}).all()
        for (rid, student_id) in rows[1:]:
            taken = {t[0] for t in bind.execute(sa.text(
                "SELECT roll_number FROM student_enrolments WHERE academic_session_id = :s"
            ), {"s": session_id}).all()}
            candidate = 1
            while candidate in taken:
                candidate += 1
            bind.execute(sa.text(
                "UPDATE student_enrolments SET roll_number = :r WHERE id = :id"
            ), {"r": candidate, "id": rid})
            renumbered += 1
            log.info(
                "0008: renumbered enrolment %s (student %s) in session %s: roll %s -> %s",
                rid, student_id, session_id, dup_roll, candidate)
    log.info("0008: renumbered %d duplicate roll-number row(s)", renumbered)

    # ---- 4. Sync students.current_roll_number with the active enrolment. ----
    sync = bind.execute(sa.text(
        "UPDATE students SET current_roll_number = ("
        "  SELECT se.roll_number FROM student_enrolments se"
        "  WHERE se.student_id = students.id AND se.is_active"
        "  ORDER BY se.created_at DESC LIMIT 1"
        ") WHERE EXISTS ("
        "  SELECT 1 FROM student_enrolments se"
        "  WHERE se.student_id = students.id AND se.is_active"
        ")"
    ))
    log.info(
        "0008: synced %s students.current_roll_number row(s) with the active enrolment",
        sync.rowcount or 0,
    )

    # Re-inspect so the guarded constraint ops below see current DB state.
    inspector = sa.inspect(bind)

    # ---- 5. Drop obsolete objects. ----
    # The old (session, section, roll) unique is superseded by the session-wide
    # (session, roll) unique. The (student, session) index is now redundant with
    # the new UNIQUE(student_id, academic_session_id) constraint (which creates
    # its own index).
    if _has_uq(inspector, "student_enrolments", "uq_enrolment_session_section_roll"):
        with op.batch_alter_table("student_enrolments") as b:
            b.drop_constraint("uq_enrolment_session_section_roll", type_="unique")
    if _has_index(inspector, "student_enrolments", "ix_enrolment_student_session"):
        with op.batch_alter_table("student_enrolments") as b:
            b.drop_index("ix_enrolment_student_session")

    # ---- 6. Add the new authoritative constraints (guarded). ----
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


def downgrade():
    raise NotImplementedError(
        "Downgrade from 0008_roll_session_unique is not supported: it would "
        "remove roll-uniqueness and one-enrolment-per-session constraints the "
        "application depends on, and undo an irreversible data renumbering / "
        "duplicate removal."
    )
