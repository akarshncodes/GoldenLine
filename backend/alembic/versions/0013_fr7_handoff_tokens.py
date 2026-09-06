"""FR-7: `qr_handoff_tokens` table

Revision ID: 0013_fr7_handoff_tokens
Revises: 0012_fr7_fr8_case_columns
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013_fr7_handoff_tokens"
down_revision: Union[str, None] = "0012_fr7_fr8_case_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "qr_handoff_tokens",
        sa.Column("token_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_qr_handoff_tokens_case"),
        sa.UniqueConstraint("token", name="uq_qr_handoff_tokens_token"),
    )
    op.create_index("ix_qr_handoff_tokens_token", "qr_handoff_tokens", ["token"])
    op.create_index("ix_qr_handoff_tokens_case_id", "qr_handoff_tokens", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_qr_handoff_tokens_case_id", table_name="qr_handoff_tokens")
    op.drop_index("ix_qr_handoff_tokens_token", table_name="qr_handoff_tokens")
    op.drop_table("qr_handoff_tokens")
