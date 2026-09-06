"""FR-18: Patient Census + Manual Admit/Discharge/Bed-Assignment.

- `patients` + `bed_assignments` tables: hospital-wide patient tracking,
  independent of the emergency case pipeline. Every QR-handoff-admitted case
  also gets a visibility-only row here (patient_type='emergency_case').
- `hospital_sync_events.related_patient_id`: ties a 'walkin_admission'/
  'walkin_discharge' audit row to the patient it was for (mirrors
  related_case_id/related_handoff_token_id for the QR-handoff path).
- Widens the `ck_hospital_sync_events_source` CHECK to allow those two new
  source values (walk-in admit/discharge into a general/ICU bed atomically
  decrement/increment the SAME live_bed_count/live_icu_count columns FR-2
  ranking and FR-3 bed-lock read — see hospital_sync.record_walkin_*).

Revision ID: 0030_fr18_patient_census
Revises: 0029_fr17_bed_categories
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0030_fr18_patient_census"
down_revision: Union[str, None] = "0029_fr17_bed_categories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "('hms_api', 'google_sheets', 'manual_counter', 'qr_handoff_admission', 'discharge_bed_released')"
_NEW = (
    "('hms_api', 'google_sheets', 'manual_counter', 'qr_handoff_admission', "
    "'discharge_bed_released', 'walkin_admission', 'walkin_discharge')"
)


def upgrade() -> None:
    op.add_column(
        "hospital_sync_events", sa.Column("related_patient_id", sa.String(length=36), nullable=True)
    )
    with op.batch_alter_table("hospital_sync_events") as batch_op:
        batch_op.drop_constraint("ck_hospital_sync_events_source", type_="check")
        batch_op.create_check_constraint("ck_hospital_sync_events_source", f"source IN {_NEW}")

    op.create_table(
        "patients",
        sa.Column("patient_id", sa.String(length=36), primary_key=True),
        sa.Column("hospital_id", sa.String(length=32), sa.ForeignKey("hospitals.hospital_id"), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("approx_age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("phone_number", sa.String(length=10), nullable=True),
        sa.Column("patient_type", sa.String(length=16), nullable=False),
        sa.Column("linked_case_id", sa.String(length=36), sa.ForeignKey("cases.case_id"), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="waiting"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_patients_hospital_id", "patients", ["hospital_id"])
    op.create_index("ix_patients_linked_case_id", "patients", ["linked_case_id"])

    op.create_table(
        "bed_assignments",
        sa.Column("bed_assignment_id", sa.String(length=36), primary_key=True),
        sa.Column("patient_id", sa.String(length=36), sa.ForeignKey("patients.patient_id"), nullable=False),
        sa.Column("hospital_id", sa.String(length=32), sa.ForeignKey("hospitals.hospital_id"), nullable=False),
        sa.Column("category_code", sa.String(length=32), nullable=False),
        sa.Column("bed_label", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False, server_default="active"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.String(length=64), nullable=True),
        sa.Column("released_by", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_bed_assignments_patient_id", "bed_assignments", ["patient_id"])


def downgrade() -> None:
    op.drop_index("ix_bed_assignments_patient_id", table_name="bed_assignments")
    op.drop_table("bed_assignments")

    op.drop_index("ix_patients_linked_case_id", table_name="patients")
    op.drop_index("ix_patients_hospital_id", table_name="patients")
    op.drop_table("patients")

    with op.batch_alter_table("hospital_sync_events") as batch_op:
        batch_op.drop_constraint("ck_hospital_sync_events_source", type_="check")
        batch_op.create_check_constraint("ck_hospital_sync_events_source", f"source IN {_OLD}")
    with op.batch_alter_table("hospital_sync_events") as batch_op:
        batch_op.drop_column("related_patient_id")
