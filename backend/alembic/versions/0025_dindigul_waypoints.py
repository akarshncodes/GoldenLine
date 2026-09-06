"""Relabel the FR-4 ALS-risk waypoints (ambulance stop-off points) to real
Dindigul, Tamil Nadu localities — they were still Bengaluru-named, left over
from before this demo narrowed to a single city (see [[dindigul-real-data]]
memory). Same 5 ids (WP-01..05), content replaced; approximate real Dindigul
neighbourhood names, invented coordinates/oxygen/doctor flags (no public
source for those, same judgment-call approach as the hospitals/blood banks).

Revision ID: 0025_dindigul_waypoints
Revises: 0024_dindigul_real_data
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0025_dindigul_waypoints"
down_revision: Union[str, None] = "0024_dindigul_real_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# mirrors app/services/reference_seed.py SEED_WAYPOINTS
_WAYPOINTS = [
    ("WP-01", "Anna Nagar PHC", "PHC", 10.3745, 77.9840, True, True),
    ("WP-02", "Nagal Nagar CHC", "CHC", 10.3600, 77.9830, True, True),
    ("WP-03", "Begampur PHC", "PHC", 10.3580, 77.9740, True, False),
    ("WP-04", "Gandhiji Nagar CHC", "CHC", 10.3660, 77.9880, True, True),
    ("WP-05", "New Agraharam PHC", "PHC", 10.3710, 77.9760, False, True),
]

# mirrors migration 0009's original content, for the downgrade path
_OLD_WAYPOINTS = [
    ("WP-01", "Jayanagar PHC", "PHC", 12.9250, 77.5830, True, True),
    ("WP-02", "Indiranagar CHC", "CHC", 12.9720, 77.6400, True, True),
    ("WP-03", "Yelahanka PHC", "PHC", 13.1000, 77.5960, True, False),
    ("WP-04", "Koramangala CHC", "CHC", 12.9350, 77.6250, True, True),
    ("WP-05", "Whitefield PHC", "PHC", 12.9700, 77.7500, False, True),
]


def _apply(rows: list[tuple]) -> None:
    for wp_id, name, kind, lat, lon, has_oxygen, has_doctor in rows:
        op.execute(
            sa.text(
                "UPDATE waypoints SET name=:name, kind=:kind, latitude=:lat, "
                "longitude=:lon, has_oxygen=:oxygen, has_doctor=:doctor "
                "WHERE waypoint_id=:id"
            ).bindparams(
                name=name, kind=kind, lat=lat, lon=lon,
                oxygen=has_oxygen, doctor=has_doctor, id=wp_id,
            )
        )


def upgrade() -> None:
    _apply(_WAYPOINTS)


def downgrade() -> None:
    _apply(_OLD_WAYPOINTS)
