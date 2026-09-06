"""FR-11/FR-12: users, OTP, deletion requests, dedup + rate-limit logs

Revision ID: 0016_fr11_fr12_security
Revises: 0015_fr9_tracking_sms
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016_fr11_fr12_security"
down_revision: Union[str, None] = "0015_fr9_tracking_sms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# mirrors app/services/user_seed.py SEED_USERS
_USERS = [
    ("admin", "admin", "Platform Admin", None, None, None),
    ("control-room", "control_room", "Control Room", None, None, None),
    ("ATT-9", "attender", "Attender Ravi", "9811100009", None, None),
    ("ATT-1", "attender", "Attender Suresh", "9811100001", None, None),
    ("recep-hosp-001", "hospital_receptionist", "Reception — City Govt", None, "HOSP-001", None),
    ("recep-hosp-004", "hospital_receptionist", "Reception — Metro Care", None, "HOSP-004", None),
    ("recep-hosp-007", "hospital_receptionist", "Reception — Trauma & Burns", None, "HOSP-007", None),
    ("coord-bb-01", "blood_bank_coordinator", "Coordinator — Central Blood Bank", None, None, "BB-01"),
    ("coord-bb-02", "blood_bank_coordinator", "Coordinator — Redcross", None, None, "BB-02"),
]

_ROLES = "('family','attender','hospital_receptionist','blood_bank_coordinator','control_room','admin')"


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.add_column(sa.Column("family_user_id", sa.String(length=64), nullable=True))

    with op.batch_alter_table("sms_messages") as batch_op:
        batch_op.drop_constraint("ck_sms_messages_category", type_="check")
        batch_op.create_check_constraint(
            "ck_sms_messages_category",
            "category IN ('tracking_link', 'discharge_feedback', 'otp')",
        )

    users = op.create_table(
        "users",
        sa.Column("user_id", sa.String(length=64), primary_key=True),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("phone_number", sa.String(length=10), nullable=True),
        sa.Column("hospital_id", sa.String(length=32), nullable=True),
        sa.Column("blood_bank_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"role IN {_ROLES}", name="ck_users_role"),
    )
    op.bulk_insert(
        users,
        [
            {"user_id": u[0], "role": u[1], "display_name": u[2],
             "phone_number": u[3], "hospital_id": u[4], "blood_bank_id": u[5]}
            for u in _USERS
        ],
    )

    op.create_table(
        "otp_verifications",
        sa.Column("otp_verification_id", sa.String(length=36), primary_key=True),
        sa.Column("phone_number", sa.String(length=10), nullable=False),
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_otp_verifications_phone_number", "otp_verifications", ["phone_number"])

    op.create_table(
        "deletion_requests",
        sa.Column("deletion_request_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("requested_by", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_by", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.case_id"], name="fk_deletion_requests_case"),
        sa.CheckConstraint("status IN ('pending','processed','rejected')", name="ck_deletion_requests_status"),
    )

    op.create_table(
        "duplicate_merge_logs",
        sa.Column("merge_log_id", sa.String(length=36), primary_key=True),
        sa.Column("primary_case_id", sa.String(length=36), nullable=False),
        sa.Column("duplicate_source", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("distance_metres", sa.Float(), nullable=True),
        sa.Column("seconds_apart", sa.Integer(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["primary_case_id"], ["cases.case_id"], name="fk_duplicate_merge_logs_case"),
    )

    op.create_table(
        "rate_limit_flags",
        sa.Column("rate_limit_flag_id", sa.String(length=36), primary_key=True),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        sa.Column("flagged_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_limit_flags_source", "rate_limit_flags", ["source"])


def downgrade() -> None:
    op.drop_table("rate_limit_flags")
    op.drop_table("duplicate_merge_logs")
    op.drop_table("deletion_requests")
    op.drop_index("ix_otp_verifications_phone_number", table_name="otp_verifications")
    op.drop_table("otp_verifications")
    op.drop_table("users")
    with op.batch_alter_table("sms_messages") as batch_op:
        batch_op.drop_constraint("ck_sms_messages_category", type_="check")
        batch_op.create_check_constraint(
            "ck_sms_messages_category",
            "category IN ('tracking_link', 'discharge_feedback')",
        )
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("family_user_id")
