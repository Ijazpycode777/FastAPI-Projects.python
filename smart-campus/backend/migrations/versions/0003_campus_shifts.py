"""Campus shifts + roll-number schemes foundation.

Creates campus_shifts + roll_number_schemes tables, adds campus_shift_id to
students / student_enrolments / timetable_entries / teachers, drops the old
enrolment (session, section, roll) unique constraint (it contradicts cross-shift
roll reuse) and adds the authoritative UNIQUE(campus_shift_id, current_roll_number)
on students.

Guarded so it is safe on both fresh deploys (where 0001's create_all already
created the new schema) and existing-DB upgrades.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_campus_shifts"
down_revision = "0002_leave_student"
branch_labels = None
depends_on = None


def _has_table(inspector, name: str) -> bool:
    try:
        return inspector.has_table(name)
    except Exception:
        return name in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. campus_shifts
    if not _has_table(inspector, "campus_shifts"):
        op.create_table(
            "campus_shifts",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("name", sa.String(length=40), nullable=False),
            sa.Column("code", sa.String(length=16), nullable=False),
            sa.Column("start_time", sa.Time(), nullable=True),
            sa.Column("end_time", sa.Time(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("code", name="uq_campus_shift_code"),
        )
        op.create_index("ix_campus_shift_active", "campus_shifts", ["is_active"])

    # 2. roll_number_schemes
    if not _has_table(inspector, "roll_number_schemes"):
        op.create_table(
            "roll_number_schemes",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("campus_shift_id", sa.String(length=36), nullable=False),
            sa.Column("class_id", sa.String(length=36), nullable=False),
            sa.Column("section_id", sa.String(length=36), nullable=True),
            sa.Column("prefix", sa.String(length=16), nullable=True),
            sa.Column("min_roll", sa.Integer(), nullable=False),
            sa.Column("max_roll", sa.Integer(), nullable=False),
            sa.Column("padding", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("campus_shift_id", "class_id", "section_id", name="uq_roll_scheme_shift_class_section"),
            sa.CheckConstraint("max_roll >= min_roll", name="roll_scheme_range_check"),
        )
        op.create_index("ix_roll_scheme_class", "roll_number_schemes", ["class_id"])

    # 3. campus_shift_id columns (nullable; FKs are enforced via the model on
    # fresh deploys. We add the column only — SQLite cannot add FK constraints
    # without batch mode, and the app validates integrity in the service layer.)
    def _add_col(table: str, colname: str) -> None:
        cols = {c["name"] for c in inspector.get_columns(table)}
        if colname not in cols:
            op.add_column(table, sa.Column(colname, sa.String(length=36), nullable=True))

    _add_col("students", "campus_shift_id")
    _add_col("student_enrolments", "campus_shift_id")
    _add_col("timetable_entries", "campus_shift_id")
    _add_col("teachers", "campus_shift_id")

    # 4. Drop the old enrolment roll unique (it blocks cross-shift reuse).
    enr_uqs = {u["name"] for u in inspector.get_unique_constraints("student_enrolments")}
    if "uq_enrolment_roll" in enr_uqs:
        op.drop_constraint("uq_enrolment_roll", "student_enrolments", type_="unique")
    enr_idx = {i["name"] for i in inspector.get_indexes("student_enrolments")}
    if "ix_enrolment_section_roll" not in enr_idx:
        op.create_index("ix_enrolment_section_roll", "student_enrolments", ["section_id", "roll_number"])

    # 5. students (campus_shift_id, current_roll_number) unique + index.
    # Safe to add: legacy rows have NULL campus_shift_id, and NULLs are distinct
    # under both PostgreSQL and SQLite unique constraints.
    stu_uqs = {u["name"] for u in inspector.get_unique_constraints("students")}
    if "uq_students_shift_roll" not in stu_uqs:
        # SQLite cannot ALTER constraints on an existing table — use batch mode
        # (copy-and-move). Works on both SQLite and PostgreSQL.
        with op.batch_alter_table("students") as b:
            b.create_unique_constraint("uq_students_shift_roll", ["campus_shift_id", "current_roll_number"])
    stu_idx = {i["name"] for i in inspector.get_indexes("students")}
    if "ix_students_shift_roll" not in stu_idx:
        op.create_index("ix_students_shift_roll", "students", ["campus_shift_id", "current_roll_number"])


def downgrade():
    # Indexes drop cleanly on both SQLite and PostgreSQL.
    op.drop_index("ix_students_shift_roll", table_name="students")
    op.drop_index("ix_enrolment_section_roll", table_name="student_enrolments")
    # Columns + the students unique constraint: SQLite cannot ALTER constraints
    # or drop columns directly, so use batch mode (copy-and-move). Works on both
    # SQLite and PostgreSQL.
    with op.batch_alter_table("students") as b:
        b.drop_constraint("uq_students_shift_roll", type_="unique")
        b.drop_column("campus_shift_id")
    with op.batch_alter_table("student_enrolments") as b:
        b.drop_column("campus_shift_id")
    with op.batch_alter_table("timetable_entries") as b:
        b.drop_column("campus_shift_id")
    with op.batch_alter_table("teachers") as b:
        b.drop_column("campus_shift_id")
    op.drop_index("ix_roll_scheme_class", table_name="roll_number_schemes")
    op.drop_table("roll_number_schemes")
    op.drop_index("ix_campus_shift_active", table_name="campus_shifts")
    op.drop_table("campus_shifts")
