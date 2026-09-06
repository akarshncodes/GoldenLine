"""FR-0 Case Creation: single `cases` table (both creation paths)

Revision ID: 0002_fr0_cases
Revises: 0001_initial_setup
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_fr0_cases"
down_revision: Union[str, None] = "0001_initial_setup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("case_id", sa.String(length=36), primary_key=True),
        sa.Column("creation_path", sa.String(length=1), nullable=False),
        sa.Column("patient_name", sa.String(length=200), nullable=True),
        sa.Column("patient_approx_age", sa.Integer(), nullable=True),
        sa.Column("patient_gender", sa.String(length=10), nullable=True),
        sa.Column("family_phone_number", sa.String(length=10), nullable=True),
        sa.Column("next_of_kin_phone_number", sa.String(length=10), nullable=True),
        sa.Column("gps_latitude", sa.Float(), nullable=True),
        sa.Column("gps_longitude", sa.Float(), nullable=True),
        sa.Column("gps_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gps_source", sa.String(length=20), nullable=True),
        sa.Column("attender_id", sa.String(length=64), nullable=True),
        sa.Column("dispatched_ambulance_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("creation_path IN ('A', 'B')", name="ck_cases_creation_path"),
    )
    op.create_index("ix_cases_creation_path", "cases", ["creation_path"])
    op.create_index("ix_cases_attender_id", "cases", ["attender_id"])


def downgrade() -> None:
    op.drop_index("ix_cases_attender_id", table_name="cases")
    op.drop_index("ix_cases_creation_path", table_name="cases")
    op.drop_table("cases")
