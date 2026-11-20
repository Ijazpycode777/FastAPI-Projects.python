"""leave_records: support student leave.

Adds person_type + student_id (nullable), makes teacher_id nullable, and adds
an index on (student_id, status). A leave now targets exactly one of
student/teacher. Guarded so it is safe on both fresh deploys (where 0001's
create_all already created the new columns) and existing-DB upgrades.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_leave_student"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("leave_records")}

    if "person_type" not in cols:
        op.add_column(
            "leave_records",
            sa.Column("person_type", sa.String(length=8), nullable=False, server_default="teacher"),
        )
    if "student_id" not in cols:
        op.add_column(
            "leave_records",
            sa.Column("student_id", sa.String(length=36), nullable=True),
        )

    # teacher_id becomes nullable (a leave targets exactly one of student/teacher).
    op.alter_column("leave_records", "teacher_id", existing_type=sa.String(length=36), nullable=True)

    existing_indexes = {i["name"] for i in inspector.get_indexes("leave_records")}
    if "ix_leave_student" not in existing_indexes:
        op.create_index("ix_leave_student", "leave_records", ["student_id", "status"])


def downgrade():
    op.drop_index("ix_leave_student", table_name="leave_records")
    op.alter_column("leave_records", "teacher_id", existing_type=sa.String(length=36), nullable=False)
    op.drop_column("leave_records", "student_id")
    op.drop_column("leave_records", "person_type")
