"""FR-7/FR-8: cases clinical info + admission/discharge timestamps

Revision ID: 0012_fr7_fr8_case_columns
Revises: 0011_fr6_prep_actions
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_fr7_fr8_case_columns"
down_revision: Union[str, None] = "0011_fr6_prep_actions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(sa.Column("known_allergies", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("current_medications", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("blood_group", sa.String(length=3), nullable=True))
        batch_op.add_column(sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("admitted_by", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("discharged_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("discharged_at")
        batch_op.drop_column("admitted_by")
        batch_op.drop_column("admitted_at")
        batch_op.drop_column("blood_group")
        batch_op.drop_column("current_medications")
        batch_op.drop_column("known_allergies")
