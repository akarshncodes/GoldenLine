"""FR-2: add government scheme + final hospital selection columns to `cases`

Revision ID: 0005_fr2_case_selection
Revises: 0004_fr1_assessments
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_fr2_case_selection"
down_revision: Union[str, None] = "0004_fr1_assessments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(sa.Column("government_scheme", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("selected_hospital_id", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("selected_by", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("selected_via", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("selection_timestamp", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("selection_timestamp")
        batch_op.drop_column("selected_via")
        batch_op.drop_column("selected_by")
        batch_op.drop_column("selected_hospital_id")
        batch_op.drop_column("government_scheme")
