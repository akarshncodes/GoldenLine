"""FR-16: allow the 'discharge_bed_released' hospital_sync_events source

The admission decrement (FR-7 QR handoff) now has a counterpart: an explicit,
audited re-increment when the case is discharged (FR-8). Widen the CHECK.

Revision ID: 0021_fr16_discharge_bed_release
Revises: 0020_fr11_user_passwords
Create Date: 2026-09-04
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0021_fr16_discharge_bed_release"
down_revision: Union[str, None] = "0020_fr11_user_passwords"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "('hms_api', 'google_sheets', 'manual_counter', 'qr_handoff_admission')"
_NEW = "('hms_api', 'google_sheets', 'manual_counter', 'qr_handoff_admission', 'discharge_bed_released')"


def upgrade() -> None:
    with op.batch_alter_table("hospital_sync_events") as batch_op:
        batch_op.drop_constraint("ck_hospital_sync_events_source", type_="check")
        batch_op.create_check_constraint("ck_hospital_sync_events_source", f"source IN {_NEW}")


def downgrade() -> None:
    with op.batch_alter_table("hospital_sync_events") as batch_op:
        batch_op.drop_constraint("ck_hospital_sync_events_source", type_="check")
        batch_op.create_check_constraint("ck_hospital_sync_events_source", f"source IN {_OLD}")
