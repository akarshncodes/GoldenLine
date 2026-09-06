"""FR-17: `bed_categories` table — hospital-defined room/bed capacity beyond
general+ICU (private, semi-private, ward, isolation, ...).

Purely additive: does not touch `hospitals.live_bed_count`/`live_icu_count`,
the columns FR-2 ranking and FR-3 bed-lock read from. The emergency pipeline
never routes into these categories.

Revision ID: 0029_fr17_bed_categories
Revises: 0028_case_notes
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0029_fr17_bed_categories"
down_revision: Union[str, None] = "0028_case_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bed_categories",
        sa.Column("bed_category_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.String(length=32), sa.ForeignKey("hospitals.hospital_id"), nullable=False),
        sa.Column("category_code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("total_beds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("hospital_id", "category_code", name="uq_bed_category_hospital_code"),
    )
    op.create_index("ix_bed_categories_hospital_id", "bed_categories", ["hospital_id"])


def downgrade() -> None:
    op.drop_index("ix_bed_categories_hospital_id", table_name="bed_categories")
    op.drop_table("bed_categories")
