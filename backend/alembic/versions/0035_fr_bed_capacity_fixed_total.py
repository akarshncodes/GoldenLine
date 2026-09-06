"""Fix hospital bed dashboard: add a FIXED total_bed_count/total_icu_bed_count
per hospital, separate from live_bed_count/live_icu_count.

Bug fixed: the "Bed capacity" dashboard was showing `live_bed_count` itself as
the "total" — since every admission (QR-handoff AND FR-18 walk-in) decrements
that same column, the displayed "total" shrank on every admission instead of
staying fixed while a "reserved" count grew. `live_bed_count`/`live_icu_count`
keep their existing meaning everywhere else (current free-for-new-admission
capacity — FR-2 ranking, FR-3 bed-lock, and every sync tier still read/write
them exactly as before); only the dashboard's *display* math changes, via
app/services/bed_lock.py::availability_for_all().

Revision ID: 0035_fr_bed_capacity_fixed_total
Revises: 0034_fr22_import_sessions
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0035_fr_bed_capacity_fixed_total"
down_revision: Union[str, None] = "0034_fr22_import_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# hospital_id -> (total_bed_count, total_icu_bed_count) — the ORIGINAL seed
# live_bed_count/live_icu_count from app/services/hospital_seed.py, duplicated
# here per this project's established "migrations are frozen snapshots"
# convention (see e.g. 0008_fr4_fr5_columns, 0024_dindigul_real_data).
_HOSPITAL_TOTALS: dict[str, tuple[int, int]] = {
    "HOSP-001": (130, 28), "HOSP-002": (60, 8), "HOSP-003": (100, 20),
    "HOSP-004": (70, 12), "HOSP-005": (80, 15), "HOSP-006": (50, 6),
    "HOSP-007": (55, 8), "HOSP-008": (45, 6), "HOSP-009": (50, 7),
    "HOSP-010": (40, 8), "HOSP-011": (40, 5), "HOSP-012": (35, 5),
    "HOSP-013": (45, 6), "HOSP-014": (40, 5), "HOSP-015": (30, 4),
    "HOSP-016": (35, 4), "HOSP-017": (30, 4), "HOSP-018": (35, 5),
    "HOSP-019": (30, 4), "HOSP-020": (30, 3), "HOSP-021": (35, 4),
    "HOSP-022": (40, 6), "HOSP-023": (45, 6), "HOSP-024": (25, 3),
    "HOSP-025": (20, 2),
}


def upgrade() -> None:
    with op.batch_alter_table("hospitals") as batch_op:
        batch_op.add_column(sa.Column("total_bed_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("total_icu_bed_count", sa.Integer(), nullable=False, server_default="0"))

    conn = op.get_bind()
    for hid, (total_general, total_icu) in _HOSPITAL_TOTALS.items():
        conn.execute(
            sa.text(
                "UPDATE hospitals SET total_bed_count=:tg, total_icu_bed_count=:ti WHERE hospital_id=:hid"
            ),
            {"tg": total_general, "ti": total_icu, "hid": hid},
        )


def downgrade() -> None:
    with op.batch_alter_table("hospitals") as batch_op:
        batch_op.drop_column("total_icu_bed_count")
        batch_op.drop_column("total_bed_count")
