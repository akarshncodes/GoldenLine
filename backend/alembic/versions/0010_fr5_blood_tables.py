"""FR-5: blood_banks (+seed), blood_checks, blood_bank_holds

Revision ID: 0010_fr5_blood_tables
Revises: 0009_fr4_route_tables
Create Date: 2026-09-02
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_fr5_blood_tables"
down_revision: Union[str, None] = "0009_fr4_route_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# mirrors app/services/reference_seed.py SEED_BLOOD_BANKS
_BLOOD_BANKS = [
    ("BB-01", "Central Blood Bank", 12.9700, 77.5900,
     ["HOSP-001", "HOSP-002", "HOSP-003", "HOSP-004"],
     {"O-": 12, "O+": 30, "A+": 20, "A-": 5, "B+": 18, "B-": 4, "AB+": 6, "AB-": 3}),
    ("BB-02", "Redcross Blood Centre", 12.9400, 77.6300,
     ["HOSP-005", "HOSP-006", "HOSP-007"],
     {"O-": 8, "O+": 22, "A+": 14, "B+": 10, "AB+": 4}),
    ("BB-03", "Metro Blood Services", 12.9900, 77.6100,
     ["HOSP-008", "HOSP-009", "HOSP-010"],
     {"O-": 6, "O+": 18, "A+": 12, "B+": 9, "AB+": 3, "AB-": 2}),
]


def upgrade() -> None:
    blood_banks = op.create_table(
        "blood_banks",
        sa.Column("blood_bank_id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("linked_hospital_ids", sa.JSON(), nullable=False),
        sa.Column("stock_by_group", sa.JSON(), nullable=False),
    )
    op.bulk_insert(
        blood_banks,
        [
            {"blood_bank_id": b[0], "name": b[1], "latitude": b[2], "longitude": b[3],
             "linked_hospital_ids": b[4], "stock_by_group": b[5]}
            for b in _BLOOD_BANKS
        ],
    )

    op.create_table(
        "blood_checks",
        sa.Column("blood_check_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("hospital_id", sa.String(length=32), nullable=False),
        sa.Column("blood_requirement_flag", sa.Boolean(), nullable=False),
        sa.Column("blood_group", sa.String(length=3), nullable=True),
        sa.Column("triggered_by_symptoms", sa.JSON(), nullable=False),
        sa.Column("hospital_stock_sufficient", sa.Boolean(), nullable=False),
        sa.Column("hospital_stock_snapshot", sa.JSON(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_blood_checks_case"),
        sa.UniqueConstraint("case_id", name="uq_blood_checks_case"),
        sa.CheckConstraint(
            "outcome IN ('hospital_stock_ok', 'blood_bank_hold_requested')",
            name="ck_blood_checks_outcome",
        ),
    )

    op.create_table(
        "blood_bank_holds",
        sa.Column("blood_bank_hold_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("blood_bank_id", sa.String(length=32), nullable=False),
        sa.Column("hospital_id", sa.String(length=32), nullable=False),
        sa.Column("blood_group", sa.String(length=3), nullable=True),
        sa.Column("units_requested", sa.Integer(), nullable=False),
        sa.Column("hold_status", sa.String(length=12), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_blood_bank_holds_case"),
        sa.ForeignKeyConstraint(["blood_bank_id"], ["blood_banks.blood_bank_id"], name="fk_blood_bank_holds_bank"),
        sa.CheckConstraint(
            "hold_status IN ('pending', 'confirmed', 'rejected')", name="ck_blood_bank_holds_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("blood_bank_holds")
    op.drop_table("blood_checks")
    op.drop_table("blood_banks")
