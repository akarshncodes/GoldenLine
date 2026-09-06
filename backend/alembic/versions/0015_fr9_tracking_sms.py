"""FR-9: `case_tracking_tokens` + shared `sms_messages` log

Revision ID: 0015_fr9_tracking_sms
Revises: 0014_fr8_feedback
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015_fr9_tracking_sms"
down_revision: Union[str, None] = "0014_fr8_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sms_messages",
        sa.Column("sms_id", sa.String(length=36), primary_key=True),
        sa.Column("to_phone", sa.String(length=20), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('tracking_link', 'discharge_feedback')", name="ck_sms_messages_category"
        ),
    )
    op.create_index("ix_sms_messages_case_id", "sms_messages", ["case_id"])

    op.create_table(
        "case_tracking_tokens",
        sa.Column("tracking_token_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("token_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_case_tracking_tokens_case"),
        sa.UniqueConstraint("case_id", name="uq_case_tracking_tokens_case"),
        sa.UniqueConstraint("token", name="uq_case_tracking_tokens_token"),
    )
    op.create_index("ix_case_tracking_tokens_token", "case_tracking_tokens", ["token"])


def downgrade() -> None:
    op.drop_index("ix_case_tracking_tokens_token", table_name="case_tracking_tokens")
    op.drop_table("case_tracking_tokens")
    op.drop_index("ix_sms_messages_case_id", table_name="sms_messages")
    op.drop_table("sms_messages")
