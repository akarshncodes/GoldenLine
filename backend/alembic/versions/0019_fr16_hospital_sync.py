"""FR-16 Hospital Data Sync: sync-tier columns on `hospitals` + `hospital_sync_events`

Revision ID: 0019_fr16_hospital_sync
Revises: 0018_fr10_control_room
Create Date: 2026-09-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0019_fr16_hospital_sync"
down_revision: Union[str, None] = "0018_fr10_control_room"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# mirrors app/services/hospital_sync.py::SEED_SYNC_TIERS (guarded by test_fr4_fr5_seed_parity.py)
_SYNC_TIERS: dict[str, str] = {
    "HOSP-001": "hms_api",
    "HOSP-002": "google_sheets",
    "HOSP-003": "manual_counter",
    "HOSP-004": "google_sheets",
    "HOSP-005": "hms_api",
    "HOSP-006": "manual_counter",
    "HOSP-007": "manual_counter",
    "HOSP-008": "hms_api",
    "HOSP-009": "hms_api",
    "HOSP-010": "manual_counter",
}

_TIERS_SQL = "('hms_api', 'google_sheets', 'manual_counter')"


def upgrade() -> None:
    with op.batch_alter_table("hospitals") as batch_op:
        batch_op.add_column(
            sa.Column(
                "hospital_sync_tier", sa.String(length=16),
                nullable=False, server_default="manual_counter",
            )
        )
        batch_op.add_column(sa.Column("sheet_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_check_constraint(
            "ck_hospitals_sync_tier", f"hospital_sync_tier IN {_TIERS_SQL}"
        )

    for hospital_id, tier in _SYNC_TIERS.items():
        op.execute(
            sa.text("UPDATE hospitals SET hospital_sync_tier = :t WHERE hospital_id = :h").bindparams(
                t=tier, h=hospital_id
            )
        )

    op.create_table(
        "hospital_sync_events",
        sa.Column("sync_event_id", sa.String(length=36), primary_key=True),
        sa.Column("hospital_id", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("bed_type", sa.String(length=10), nullable=True),
        sa.Column("general_before", sa.Integer(), nullable=False),
        sa.Column("general_after", sa.Integer(), nullable=False),
        sa.Column("icu_before", sa.Integer(), nullable=False),
        sa.Column("icu_after", sa.Integer(), nullable=False),
        sa.Column("related_case_id", sa.String(length=36), nullable=True),
        sa.Column("related_handoff_token_id", sa.String(length=36), nullable=True),
        sa.Column("actor", sa.String(length=64), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["hospital_id"], ["hospitals.hospital_id"], name="fk_hospital_sync_events_hospital"
        ),
        sa.CheckConstraint(
            "source IN ('hms_api', 'google_sheets', 'manual_counter', 'qr_handoff_admission')",
            name="ck_hospital_sync_events_source",
        ),
    )
    op.create_index(
        "ix_hospital_sync_events_hospital_id", "hospital_sync_events", ["hospital_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_hospital_sync_events_hospital_id", table_name="hospital_sync_events")
    op.drop_table("hospital_sync_events")
    with op.batch_alter_table("hospitals") as batch_op:
        batch_op.drop_constraint("ck_hospitals_sync_tier", type_="check")
        batch_op.drop_column("last_synced_at")
        batch_op.drop_column("sheet_url")
        batch_op.drop_column("hospital_sync_tier")
