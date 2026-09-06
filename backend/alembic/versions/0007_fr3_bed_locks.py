"""FR-3 Bed Lock: `bed_locks` + `conflict_logs` tables

Revision ID: 0007_fr3_bed_locks
Revises: 0006_fr2_hospitals
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_fr3_bed_locks"
down_revision: Union[str, None] = "0006_fr2_hospitals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bed_locks",
        sa.Column("bed_lock_id", sa.String(length=36), primary_key=True),
        sa.Column("hospital_id", sa.String(length=32), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("bed_type", sa.String(length=10), nullable=False),
        sa.Column("lock_status", sa.String(length=10), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["hospital_id"], ["hospitals.hospital_id"], name="fk_bed_locks_hospital"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_bed_locks_case"),
        sa.CheckConstraint("bed_type IN ('general', 'ICU')", name="ck_bed_locks_bed_type"),
        sa.CheckConstraint("lock_status IN ('active', 'released')", name="ck_bed_locks_lock_status"),
    )
    op.create_index(
        "ix_bed_locks_hospital_type_status",
        "bed_locks",
        ["hospital_id", "bed_type", "lock_status"],
    )
    # A case may hold at most one active bed lock at a time.
    op.create_index(
        "uq_bed_locks_one_active_per_case",
        "bed_locks",
        ["case_id"],
        unique=True,
        sqlite_where=sa.text("lock_status = 'active'"),
        postgresql_where=sa.text("lock_status = 'active'"),
    )

    op.create_table(
        "conflict_logs",
        sa.Column("conflict_log_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id_a", sa.String(length=36), nullable=False),
        sa.Column("case_id_b", sa.String(length=36), nullable=True),
        sa.Column("hospital_id", sa.String(length=32), nullable=False),
        sa.Column("bed_type", sa.String(length=10), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("bed_type IN ('general', 'ICU')", name="ck_conflict_logs_bed_type"),
    )


def downgrade() -> None:
    op.drop_table("conflict_logs")
    op.drop_index("uq_bed_locks_one_active_per_case", table_name="bed_locks")
    op.drop_index("ix_bed_locks_hospital_type_status", table_name="bed_locks")
    op.drop_table("bed_locks")
