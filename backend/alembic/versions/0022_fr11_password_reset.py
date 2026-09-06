"""FR-11: staff "forgot password" — `password_reset_tokens` table +
allow 'password_reset' SMS category

Revision ID: 0022_fr11_password_reset
Revises: 0021_fr16_discharge_bed_release
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0022_fr11_password_reset"
down_revision: Union[str, None] = "0021_fr16_discharge_bed_release"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALL = "('tracking_link', 'discharge_feedback', 'otp', 'critical_update', 'password_reset')"
_OLD = "('tracking_link', 'discharge_feedback', 'otp', 'critical_update')"


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("reset_token_id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.user_id"], name="fk_password_reset_tokens_user"
        ),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    with op.batch_alter_table("sms_messages") as batch_op:
        batch_op.drop_constraint("ck_sms_messages_category", type_="check")
        batch_op.create_check_constraint("ck_sms_messages_category", f"category IN {_ALL}")


def downgrade() -> None:
    with op.batch_alter_table("sms_messages") as batch_op:
        batch_op.drop_constraint("ck_sms_messages_category", type_="check")
        batch_op.create_check_constraint("ck_sms_messages_category", f"category IN {_OLD}")

    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
