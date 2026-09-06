"""FR-10 Control Room: `flags` + `hospital_bed_reports` tables

Revision ID: 0018_fr10_control_room
Revises: 0017_fr13_sms_fallback_category
Create Date: 2026-09-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0018_fr10_control_room"
down_revision: Union[str, None] = "0017_fr13_sms_fallback_category"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flags",
        sa.Column("flag_id", sa.String(length=36), primary_key=True),
        sa.Column("flag_type", sa.String(length=16), nullable=False),
        sa.Column("related_case_ids", sa.JSON(), nullable=False),
        sa.Column("related_hospital_id", sa.String(length=32), nullable=True),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("escalated_to", sa.String(length=200), nullable=False),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=64), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "flag_type IN ('anomaly', 'conflict', 'reconciliation')",
            name="ck_flags_flag_type",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'escalated', 'resolved')", name="ck_flags_status"
        ),
    )
    op.create_index("ix_flags_dedup_key", "flags", ["dedup_key"])

    op.create_table(
        "hospital_bed_reports",
        sa.Column("hospital_id", sa.String(length=32), primary_key=True),
        sa.Column("reported_general_in_use", sa.Integer(), nullable=False),
        sa.Column("reported_icu_in_use", sa.Integer(), nullable=False),
        sa.Column("reported_by", sa.String(length=64), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id"], ["hospitals.hospital_id"], name="fk_hospital_bed_reports_hospital"
        ),
    )


def downgrade() -> None:
    op.drop_table("hospital_bed_reports")
    op.drop_index("ix_flags_dedup_key", table_name="flags")
    op.drop_table("flags")
