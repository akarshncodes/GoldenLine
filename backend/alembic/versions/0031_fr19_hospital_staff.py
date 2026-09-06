"""FR-19: `hospital_staff` table — doctor/staff roster + on-duty status.

A lightweight, hospital-managed roster: no new User rows, no new Role, no
login for individual staff — the hospital_receptionist/admin manage this on
their behalf. Soft-delete only (`is_active`), preserving history for FR-20
staff attendance records that will reference `staff_id`.

Revision ID: 0031_fr19_hospital_staff
Revises: 0030_fr18_patient_census
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0031_fr19_hospital_staff"
down_revision: Union[str, None] = "0030_fr18_patient_census"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hospital_staff",
        sa.Column("staff_id", sa.String(length=36), primary_key=True),
        sa.Column("hospital_id", sa.String(length=32), sa.ForeignKey("hospitals.hospital_id"), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("staff_category", sa.String(length=16), nullable=False),
        sa.Column("specialty", sa.String(length=100), nullable=True),
        sa.Column("phone_number", sa.String(length=10), nullable=True),
        sa.Column("on_duty_status", sa.String(length=10), nullable=False, server_default="off_duty"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_hospital_staff_hospital_id", "hospital_staff", ["hospital_id"])


def downgrade() -> None:
    op.drop_index("ix_hospital_staff_hospital_id", table_name="hospital_staff")
    op.drop_table("hospital_staff")
