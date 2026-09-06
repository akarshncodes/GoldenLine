"""FR-8: `feedback_invites` + `case_feedback` (unique constraint on case_id)

Revision ID: 0014_fr8_feedback
Revises: 0013_fr7_handoff_tokens
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014_fr8_feedback"
down_revision: Union[str, None] = "0013_fr7_handoff_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feedback_invites",
        sa.Column("invite_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("link", sa.String(length=300), nullable=False),
        sa.Column("recipient_phone", sa.String(length=10), nullable=True),
        sa.Column("sms_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_feedback_invites_case"),
        sa.UniqueConstraint("case_id", name="uq_feedback_invites_case"),
        sa.UniqueConstraint("token", name="uq_feedback_invites_token"),
    )
    op.create_index("ix_feedback_invites_token", "feedback_invites", ["token"])

    op.create_table(
        "case_feedback",
        sa.Column("feedback_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("hospital_id", sa.String(length=32), nullable=True),
        sa.Column("wait_time_tag", sa.Integer(), nullable=False),
        sa.Column("staff_behavior_tag", sa.Integer(), nullable=False),
        sa.Column("cleanliness_tag", sa.Integer(), nullable=False),
        sa.Column("billing_tag", sa.Integer(), nullable=False),
        sa.Column("ready_as_shown_tag", sa.String(length=10), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_case_feedback_case"),
        # FR-8 rule: one feedback submission per case, enforced by the database.
        sa.UniqueConstraint("case_id", name="uq_case_feedback_case"),
        sa.CheckConstraint(
            "wait_time_tag BETWEEN 1 AND 5 AND staff_behavior_tag BETWEEN 1 AND 5 "
            "AND cleanliness_tag BETWEEN 1 AND 5 AND billing_tag BETWEEN 1 AND 5",
            name="ck_case_feedback_star_ranges",
        ),
        sa.CheckConstraint(
            "ready_as_shown_tag IN ('yes', 'no', 'somewhat')",
            name="ck_case_feedback_ready_as_shown",
        ),
    )


def downgrade() -> None:
    op.drop_table("case_feedback")
    op.drop_index("ix_feedback_invites_token", table_name="feedback_invites")
    op.drop_table("feedback_invites")
