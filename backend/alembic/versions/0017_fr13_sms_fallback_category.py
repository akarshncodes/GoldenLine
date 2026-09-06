"""FR-13: allow 'critical_update' SMS category (data-down fallback channel)

Revision ID: 0017_fr13_sms_fallback_category
Revises: 0016_fr11_fr12_security
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0017_fr13_sms_fallback_category"
down_revision: Union[str, None] = "0016_fr11_fr12_security"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ALL = "('tracking_link', 'discharge_feedback', 'otp', 'critical_update')"
_OLD = "('tracking_link', 'discharge_feedback', 'otp')"


def upgrade() -> None:
    with op.batch_alter_table("sms_messages") as batch_op:
        batch_op.drop_constraint("ck_sms_messages_category", type_="check")
        batch_op.create_check_constraint("ck_sms_messages_category", f"category IN {_ALL}")


def downgrade() -> None:
    with op.batch_alter_table("sms_messages") as batch_op:
        batch_op.drop_constraint("ck_sms_messages_category", type_="check")
        batch_op.create_check_constraint("ck_sms_messages_category", f"category IN {_OLD}")
