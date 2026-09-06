"""FR-20: `staff_attendance` table — clock-in/clock-out log.

Deliberately separate from FR-19's `hospital_staff.on_duty_status` flag: this
is a time-stamped history, not just a current-state field. Clock-in/out keeps
`on_duty_status` in sync via an explicit service call, not a DB trigger.

Revision ID: 0032_fr20_staff_attendance
Revises: 0031_fr19_hospital_staff
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0032_fr20_staff_attendance"
down_revision: Union[str, None] = "0031_fr19_hospital_staff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff_attendance",
        sa.Column("attendance_id", sa.String(length=36), primary_key=True),
        sa.Column("staff_id", sa.String(length=36), sa.ForeignKey("hospital_staff.staff_id"), nullable=False),
        sa.Column("hospital_id", sa.String(length=32), sa.ForeignKey("hospitals.hospital_id"), nullable=False),
        sa.Column("clock_in_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shift_label", sa.String(length=50), nullable=True),
        sa.Column("recorded_by", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_staff_attendance_staff_id", "staff_attendance", ["staff_id"])


def downgrade() -> None:
    op.drop_index("ix_staff_attendance_staff_id", table_name="staff_attendance")
    op.drop_table("staff_attendance")
