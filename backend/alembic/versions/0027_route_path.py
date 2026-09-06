"""Map view: add `case_routes.route_path`, a drawable [[lat, lon], ...] list.

Populated going forward by app/services/route.py from whichever routing tier
answered (Google Maps polyline decoded, OSRM's GeoJSON coordinates, or the
straight-line stub) — see app/services/maps.py. Existing rows get NULL; the
client treats a missing path as "no line to draw", which was already true for
every case created before this migration.

Revision ID: 0027_route_path
Revises: 0026_fix_hlp001_hlp002_passwords
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0027_route_path"
down_revision: Union[str, None] = "0026_fix_hlp001_hlp002_passwords"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("case_routes") as batch_op:
        batch_op.add_column(sa.Column("route_path", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("case_routes") as batch_op:
        batch_op.drop_column("route_path")
