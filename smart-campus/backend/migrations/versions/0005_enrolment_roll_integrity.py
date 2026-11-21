"""Finalize enrolment roll uniqueness after the shifts removal.

``0004_drop_campus_shifts`` added UNIQUE(academic_session_id, section_id,
roll_number) on ``student_enrolments`` only when no duplicate rows existed. On
databases that ran the original shifts model, duplicate (session, section, roll)
triples can remain after ``campus_shift_id`` was dropped — rolls used to be
scoped to (campus_shift, section), so the same roll number could legitimately
appear in different shifts within one section. Once the shift dimension was
removed those rows collapse into duplicates, and 0004 intentionally skipped the
constraint rather than fail.

This migration resolves those duplicates deterministically — for each duplicate
group the earliest row keeps its roll and each later row is moved to the
smallest unused roll in the same (academic_session, section). No enrolment rows
are deleted and no student loses a roll (only duplicates are renumbered). It
then adds the unique constraint if it is still missing.

Idempotent and guarded: safe on fresh databases (no duplicates -> no-op, the
constraint already exists from 0001's create_all) and on existing upgraded
databases. Does not mutate migration history.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_enrolment_roll_integrity"
down_revision = "0004_drop_campus_shifts"
branch_labels = None
depends_on = None


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


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_table(inspector, "student_enrolments"):
        return

    # 1. Renumber duplicate (academic_session_id, section_id, roll_number) rows.
    #    Keep the earliest row (by created_at, then id) in each duplicate group;
    #    move every later row to the smallest positive roll not yet used in the
    #    same (academic_session, section). Each UPDATE is visible to the next
    #    iteration within the same transaction, so renumbering is conflict-free.
    dup_groups = bind.execute(sa.text(
        "SELECT academic_session_id, section_id, roll_number "
        "FROM student_enrolments "
        "GROUP BY academic_session_id, section_id, roll_number "
        "HAVING COUNT(*) > 1"
    )).all()
    for session_id, section_id, dup_roll in dup_groups:
        # The conflicting rows for THIS duplicate group only (same roll number).
        # Ordered deterministically so the earliest row keeps the roll.
        rows = bind.execute(sa.text(
            "SELECT id FROM student_enrolments "
            "WHERE academic_session_id = :s AND section_id = :sec AND roll_number = :r "
            "ORDER BY created_at, id"
        ), {"s": session_id, "sec": section_id, "r": dup_roll}).all()
        # rows[0] keeps its roll; renumber the rest.
        for (rid,) in rows[1:]:
            taken = {
                t[0] for t in bind.execute(sa.text(
                    "SELECT roll_number FROM student_enrolments "
                    "WHERE academic_session_id = :s AND section_id = :sec"
                ), {"s": session_id, "sec": section_id}).all()
            }
            candidate = 1
            while candidate in taken:
                candidate += 1
            bind.execute(sa.text(
                "UPDATE student_enrolments SET roll_number = :r WHERE id = :id"
            ), {"r": candidate, "id": rid})

    # 2. Add the authoritative roll-unique constraint if it is still missing
    #    (0004 skipped it when duplicates existed; after step 1 there are none).
    if not _has_uq(inspector, "student_enrolments", "uq_enrolment_session_section_roll"):
        with op.batch_alter_table("student_enrolments") as b:
            b.create_unique_constraint(
                "uq_enrolment_session_section_roll",
                ["academic_session_id", "section_id", "roll_number"],
            )


def downgrade():
    # Dropping a data-integrity constraint that the application relies on is not
    # supported. The renumbered roll numbers are real data changes and are not
    # reversible without the original (lost) shift context.
    raise NotImplementedError(
        "Downgrade from 0005_enrolment_roll_integrity is not supported: it would "
        "remove a roll-uniqueness constraint the application depends on and undo "
        "an irreversible data renumbering."
    )
