"""Drop campus shifts + roll-number schemes.

Removes the campus_shifts / roll_number_schemes tables, the campus_shift_id
columns from students / student_enrolments / timetable_entries / teachers, and
the (campus_shift_id, current_roll_number) unique + index on students. Roll
numbers are now auto-assigned and unique within (academic_session, section), so
this migration also adds the authoritative
UNIQUE(academic_session_id, section_id, roll_number) on student_enrolments.

Guarded so it is safe on fresh deploys (where the shifts feature was never
created by 0001's create_all) and on existing-DB upgrades that already ran
0003. The enrolment unique is only added when no duplicate (session, section,
roll) rows exist — legacy shift-scoped data can otherwise conflict, and the
application-layer auto-assignment keeps rolls unique going forward regardless.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_drop_campus_shifts"
down_revision = "0003_campus_shifts"
branch_labels = None
depends_on = None


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


def _has_uq(inspector, table: str, name: str) -> bool:
    try:
        return name in {u["name"] for u in inspector.get_unique_constraints(table)}
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Drop students (campus_shift_id, current_roll_number) index + unique.
    if _has_table(inspector, "students"):
        if _has_index(inspector, "students", "ix_students_shift_roll"):
            op.drop_index("ix_students_shift_roll", table_name="students")
        if _has_uq(inspector, "students", "uq_students_shift_roll"):
            with op.batch_alter_table("students") as b:
                b.drop_constraint("uq_students_shift_roll", type_="unique")

    # 2. Drop campus_shift_id columns (batch mode for SQLite compatibility).
    for table in ("students", "student_enrolments", "timetable_entries", "teachers"):
        if _has_table(inspector, table) and _has_col(inspector, table, "campus_shift_id"):
            with op.batch_alter_table(table) as b:
                b.drop_column("campus_shift_id")

    # 3. Add the new enrolment (academic_session, section, roll) unique — only
    # when no duplicate rows exist, so legacy shift-scoped data cannot block
    # the upgrade. The application auto-assigns rolls uniquely regardless.
    if (
        _has_table(inspector, "student_enrolments")
        and not _has_uq(inspector, "student_enrolments", "uq_enrolment_session_section_roll")
    ):
        dup = bind.execute(sa.text(
            "SELECT COUNT(*) FROM ("
            "SELECT academic_session_id, section_id, roll_number FROM student_enrolments "
            "GROUP BY academic_session_id, section_id, roll_number HAVING COUNT(*) > 1"
            ") d"
        )).scalar_one()
        if (dup or 0) == 0:
            with op.batch_alter_table("student_enrolments") as b:
                b.create_unique_constraint(
                    "uq_enrolment_session_section_roll",
                    ["academic_session_id", "section_id", "roll_number"],
                )

    # 4. Drop roll_number_schemes + campus_shifts tables (and their indexes).
    if _has_table(inspector, "roll_number_schemes"):
        if _has_index(inspector, "roll_number_schemes", "ix_roll_scheme_class"):
            op.drop_index("ix_roll_scheme_class", table_name="roll_number_schemes")
        op.drop_table("roll_number_schemes")
    if _has_table(inspector, "campus_shifts"):
        if _has_index(inspector, "campus_shifts", "ix_campus_shift_active"):
            op.drop_index("ix_campus_shift_active", table_name="campus_shifts")
        op.drop_table("campus_shifts")


def downgrade():
    # The campus-shifts feature has been permanently removed from the
    # application; recreating it is out of scope. Downgrade is intentionally
    # UNSUPPORTED: raise rather than silently leave the schema and the
    # alembic_version table in disagreement (a no-op downgrade would mark the
    # DB as reverted to 0003 while the shifts tables stay dropped).
    raise NotImplementedError(
        "Downgrade from 0004_drop_campus_shifts is not supported: the campus-shifts "
        "feature has been removed from the application."
    )
