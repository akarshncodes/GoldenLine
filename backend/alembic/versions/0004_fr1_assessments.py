"""FR-1 On-Scene Assessment: `assessments` table (1:1 with cases)

Revision ID: 0004_fr1_assessments
Revises: 0003_sos_trigger_coords
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_fr1_assessments"
down_revision: Union[str, None] = "0003_sos_trigger_coords"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("assessment_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("criticality_level", sa.String(length=16), nullable=False),
        sa.Column("symptom_checklist", sa.JSON(), nullable=False),
        sa.Column("input_method", sa.String(length=16), nullable=False),
        sa.Column("raw_voice_transcript", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_assessments_case_id"),
        sa.UniqueConstraint("case_id", name="uq_assessments_case_id"),
        sa.CheckConstraint(
            "criticality_level IN ('Critical', 'Serious', 'Stable')",
            name="ck_assessments_criticality_level",
        ),
        sa.CheckConstraint(
            "input_method IN ('checklist', 'voice')",
            name="ck_assessments_input_method",
        ),
    )


def downgrade() -> None:
    op.drop_table("assessments")
