"""FR-4: case_routes, traffic_alerts, waypoints (+seed), waypoint_suggestions

Revision ID: 0009_fr4_route_tables
Revises: 0008_fr4_fr5_columns
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_fr4_route_tables"
down_revision: Union[str, None] = "0008_fr4_fr5_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# mirrors app/services/reference_seed.py SEED_WAYPOINTS
_WAYPOINTS = [
    ("WP-01", "Jayanagar PHC", "PHC", 12.9250, 77.5830, True, True),
    ("WP-02", "Indiranagar CHC", "CHC", 12.9720, 77.6400, True, True),
    ("WP-03", "Yelahanka PHC", "PHC", 13.1000, 77.5960, True, False),
    ("WP-04", "Koramangala CHC", "CHC", 12.9350, 77.6250, True, True),
    ("WP-05", "Whitefield PHC", "PHC", 12.9700, 77.7500, False, True),
]


def upgrade() -> None:
    op.create_table(
        "case_routes",
        sa.Column("route_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("hospital_id", sa.String(length=32), nullable=False),
        sa.Column("origin_latitude", sa.Float(), nullable=True),
        sa.Column("origin_longitude", sa.Float(), nullable=True),
        sa.Column("destination_latitude", sa.Float(), nullable=True),
        sa.Column("destination_longitude", sa.Float(), nullable=True),
        sa.Column("route_polyline", sa.Text(), nullable=False),
        sa.Column("route_source", sa.String(length=20), nullable=False),
        sa.Column("route_note", sa.Text(), nullable=True),
        sa.Column("eta_minutes", sa.Integer(), nullable=False),
        sa.Column("eta_min_minutes", sa.Integer(), nullable=False),
        sa.Column("eta_max_minutes", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_case_routes_case"),
        sa.UniqueConstraint("case_id", name="uq_case_routes_case"),
    )

    op.create_table(
        "traffic_alerts",
        sa.Column("traffic_alert_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("hospital_id", sa.String(length=32), nullable=False),
        sa.Column("route_polyline", sa.Text(), nullable=False),
        sa.Column("eta_minutes", sa.Integer(), nullable=False),
        sa.Column("eta_min_minutes", sa.Integer(), nullable=False),
        sa.Column("eta_max_minutes", sa.Integer(), nullable=False),
        sa.Column("traffic_alert_recipients", sa.JSON(), nullable=False),
        sa.Column("traffic_alert_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_traffic_alerts_case"),
        sa.UniqueConstraint("case_id", name="uq_traffic_alerts_case"),
    )

    waypoints = op.create_table(
        "waypoints",
        sa.Column("waypoint_id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("kind", sa.String(length=3), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("has_oxygen", sa.Boolean(), nullable=False),
        sa.Column("has_doctor", sa.Boolean(), nullable=False),
        sa.CheckConstraint("kind IN ('PHC', 'CHC')", name="ck_waypoints_kind"),
    )
    op.bulk_insert(
        waypoints,
        [
            {"waypoint_id": w[0], "name": w[1], "kind": w[2], "latitude": w[3],
             "longitude": w[4], "has_oxygen": w[5], "has_doctor": w[6]}
            for w in _WAYPOINTS
        ],
    )

    op.create_table(
        "waypoint_suggestions",
        sa.Column("waypoint_suggestion_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("waypoint_id", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("suggested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_waypoint_suggestions_case"),
        sa.ForeignKeyConstraint(["waypoint_id"], ["waypoints.waypoint_id"], name="fk_waypoint_suggestions_waypoint"),
        sa.UniqueConstraint("case_id", name="uq_waypoint_suggestions_case"),
        sa.CheckConstraint(
            "status IN ('suggested', 'accepted', 'declined')", name="ck_waypoint_suggestions_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("waypoint_suggestions")
    op.drop_table("waypoints")
    op.drop_table("traffic_alerts")
    op.drop_table("case_routes")
