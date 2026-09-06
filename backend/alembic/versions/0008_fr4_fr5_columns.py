"""FR-4/FR-5: cases.ambulance_level; hospitals geo + blood stock (backfilled)

Revision ID: 0008_fr4_fr5_columns
Revises: 0007_fr3_bed_locks
Create Date: 2026-09-02
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_fr4_fr5_columns"
down_revision: Union[str, None] = "0007_fr3_bed_locks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# id -> (latitude, longitude, blood_stock_by_group)   — mirrors app/services/hospital_seed.py
_HOSPITAL_EXTRAS: dict[str, tuple[float, float, dict]] = {
    "HOSP-001": (12.9784, 77.5920, {"O-": 1, "O+": 6, "A+": 4, "B+": 3, "AB+": 1}),
    "HOSP-002": (12.9350, 77.6250, {"O-": 0, "O+": 5, "A+": 3}),
    "HOSP-003": (12.8900, 77.5300, {"O-": 0, "O+": 2}),
    "HOSP-004": (12.9950, 77.5850, {"O-": 4, "O+": 9, "A+": 6, "B+": 5}),
    "HOSP-005": (12.9550, 77.6400, {"O-": 5, "O+": 10, "A+": 6, "B+": 4, "AB+": 2}),
    "HOSP-006": (13.0200, 77.5600, {"O-": 2, "O+": 6}),
    "HOSP-007": (12.9450, 77.5550, {"O-": 6, "O+": 12, "A+": 8, "B+": 6, "AB+": 3, "AB-": 2}),
    "HOSP-008": (12.9820, 77.6100, {"O-": 3, "O+": 8, "A+": 5}),
    "HOSP-009": (12.9680, 77.5990, {"O-": 4, "O+": 11, "A+": 7, "B+": 6, "AB+": 3}),
    "HOSP-010": (12.9100, 77.6500, {"O-": 1, "O+": 4}),
}


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(
            sa.Column("ambulance_level", sa.String(length=3), nullable=False, server_default="BLS")
        )

    with op.batch_alter_table("hospitals") as batch_op:
        batch_op.add_column(sa.Column("latitude", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("longitude", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("blood_stock_by_group", sa.JSON(), nullable=False, server_default="{}")
        )

    conn = op.get_bind()
    for hid, (lat, lon, stock) in _HOSPITAL_EXTRAS.items():
        conn.execute(
            sa.text(
                "UPDATE hospitals SET latitude=:lat, longitude=:lon, "
                "blood_stock_by_group=:stock WHERE hospital_id=:hid"
            ),
            {"lat": lat, "lon": lon, "stock": json.dumps(stock), "hid": hid},
        )


def downgrade() -> None:
    with op.batch_alter_table("hospitals") as batch_op:
        batch_op.drop_column("blood_stock_by_group")
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("ambulance_level")
