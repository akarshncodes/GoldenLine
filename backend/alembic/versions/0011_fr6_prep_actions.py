"""FR-6 Hospital Pre-Arrival Preparation: `prep_actions` table

Revision ID: 0011_fr6_prep_actions
Revises: 0010_fr5_blood_tables
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_fr6_prep_actions"
down_revision: Union[str, None] = "0010_fr5_blood_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prep_actions",
        sa.Column("prep_action_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("hospital_id", sa.String(length=32), nullable=False),
        sa.Column("action_type", sa.String(length=14), nullable=False),
        sa.Column("action_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("suggested_department", sa.String(length=64), nullable=True),
        sa.Column("triggered_by_symptom", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("confirmed_by", sa.String(length=64), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_prep_actions_case"),
        sa.UniqueConstraint("case_id", "action_key", name="uq_prep_actions_case_action"),
        sa.CheckConstraint(
            "action_type IN ('baseline', 'symptom_based')", name="ck_prep_actions_action_type"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed')", name="ck_prep_actions_status"
        ),
    )
    op.create_index("ix_prep_actions_case_id", "prep_actions", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_prep_actions_case_id", table_name="prep_actions")
    op.drop_table("prep_actions")
