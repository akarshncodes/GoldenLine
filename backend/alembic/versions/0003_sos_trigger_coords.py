"""FR-0: add audit-only SOS trigger coordinates to `cases` (Path A)

These record what the family's phone reported at SOS time (used only to find an
ambulance). They are NOT the authoritative case location (see FR-0 line 85);
that stays in gps_latitude/gps_longitude and always comes from the attender device.

Revision ID: 0003_sos_trigger_coords
Revises: 0002_fr0_cases
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_sos_trigger_coords"
down_revision: Union[str, None] = "0002_fr0_cases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(sa.Column("sos_trigger_latitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("sos_trigger_longitude", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("sos_trigger_timestamp", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("sos_trigger_timestamp")
        batch_op.drop_column("sos_trigger_longitude")
        batch_op.drop_column("sos_trigger_latitude")
