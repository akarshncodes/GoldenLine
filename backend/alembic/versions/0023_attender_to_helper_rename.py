"""Rename "attender" to "helper" everywhere, and auto-link each mock ambulance
to a fixed helper account.

The person who rides with the ambulance driver and works the case is called a
"helper" throughout the app now (was "attender"). Renames:
  - `cases.attender_id` column -> `cases.helper_id` (+ its index)
  - `Role.attender` -> `Role.helper` (users.role CHECK constraint + existing rows)
  - seeded demo accounts ATT-9 -> HLP-001, ATT-1 -> HLP-002, plus 3 new accounts
    HLP-003/004/005 so every one of the 5 mock ambulances
    (app/services/ambulance.py FAKE_AMBULANCES) has its own helper login
  - stored `cases.gps_source` value 'attender_device' -> 'helper_device'
  - stored `cases.selected_via` values 'attender_confirm'/'family_choice' ->
    'helper_confirm' (hospital selection is helper-only now, both paths)

Revision ID: 0023_attender_to_helper_rename
Revises: 0022_fr11_password_reset
Create Date: 2026-09-04
"""
import base64
import hashlib
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0023_attender_to_helper_rename"
down_revision: Union[str, None] = "0022_fr11_password_reset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ROLES = "('family','attender','hospital_receptionist','blood_bank_coordinator','control_room','admin')"
_NEW_ROLES = "('family','helper','hospital_receptionist','blood_bank_coordinator','control_room','admin')"
# Transitional: allows both old and new role values while in-place rows are updated.
_BOTH_ROLES = "('family','attender','helper','hospital_receptionist','blood_bank_coordinator','control_room','admin')"

# New helper accounts this migration adds outright (HLP-001/002 already existed
# as ATT-9/ATT-1 and are handled by the rename below, not inserted again here).
_NEW_HELPERS = [
    ("HLP-003", "Helper Anil", "9811100003"),
    ("HLP-004", "Helper Murugan", "9811100004"),
    ("HLP-005", "Helper Debashish", "9811100005"),
]
_DEV_PASSWORD_SUFFIX = "sih2026"   # mirrors user_seed._DEV_PASSWORD_SUFFIX
_PBKDF2_ALGO = "pbkdf2_sha256"     # mirrors security._PBKDF2_ALGO
_PBKDF2_ITERATIONS = 480_000       # mirrors security._PBKDF2_ITERATIONS


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _hash(plain: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}${_b64url(salt)}${_b64url(digest)}"


def upgrade() -> None:
    # --- cases.attender_id -> cases.helper_id ---
    with op.batch_alter_table("cases") as batch_op:
        batch_op.alter_column("attender_id", new_column_name="helper_id")
    op.drop_index("ix_cases_attender_id", table_name="cases")
    op.create_index("ix_cases_helper_id", "cases", ["helper_id"])

    op.execute(sa.text("UPDATE cases SET gps_source = 'helper_device' WHERE gps_source = 'attender_device'"))
    op.execute(
        sa.text(
            "UPDATE cases SET selected_via = 'helper_confirm' "
            "WHERE selected_via IN ('attender_confirm', 'family_choice')"
        )
    )

    # --- users.role: 'attender' -> 'helper' (CHECK constraint + existing rows) ---
    # A transitional constraint allows both values while rows are updated, since
    # neither the old nor the final constraint alone permits both at once.
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint("ck_users_role", f"role IN {_BOTH_ROLES}")
    op.execute(sa.text("UPDATE users SET role = 'helper' WHERE role = 'attender'"))
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint("ck_users_role", f"role IN {_NEW_ROLES}")

    # --- seeded ids: ATT-9 -> HLP-001, ATT-1 -> HLP-002 (+ their FK references) ---
    op.execute(sa.text("UPDATE users SET user_id = 'HLP-001', display_name = 'Helper Ravi' WHERE user_id = 'ATT-9'"))
    op.execute(sa.text("UPDATE users SET user_id = 'HLP-002', display_name = 'Helper Suresh' WHERE user_id = 'ATT-1'"))
    op.execute(sa.text("UPDATE cases SET helper_id = 'HLP-001' WHERE helper_id = 'ATT-9'"))
    op.execute(sa.text("UPDATE cases SET helper_id = 'HLP-002' WHERE helper_id = 'ATT-1'"))
    op.execute(sa.text("UPDATE password_reset_tokens SET user_id = 'HLP-001' WHERE user_id = 'ATT-9'"))
    op.execute(sa.text("UPDATE password_reset_tokens SET user_id = 'HLP-002' WHERE user_id = 'ATT-1'"))

    # --- 3 new helper accounts, one per remaining mock ambulance ---
    users = sa.table(
        "users",
        sa.column("user_id", sa.String),
        sa.column("role", sa.String),
        sa.column("display_name", sa.String),
        sa.column("phone_number", sa.String),
    )
    op.bulk_insert(
        users,
        [
            {"user_id": uid, "role": "helper", "display_name": name, "phone_number": phone}
            for uid, name, phone in _NEW_HELPERS
        ],
    )
    for uid, _name, _phone in _NEW_HELPERS:
        op.execute(
            sa.text("UPDATE users SET password_hash = :h WHERE user_id = :u").bindparams(
                h=_hash(f"{uid}.{_DEV_PASSWORD_SUFFIX}"), u=uid
            )
        )


def downgrade() -> None:
    for uid, _name, _phone in _NEW_HELPERS:
        op.execute(sa.text("DELETE FROM users WHERE user_id = :u").bindparams(u=uid))

    op.execute(sa.text("UPDATE password_reset_tokens SET user_id = 'ATT-9' WHERE user_id = 'HLP-001'"))
    op.execute(sa.text("UPDATE password_reset_tokens SET user_id = 'ATT-1' WHERE user_id = 'HLP-002'"))
    op.execute(sa.text("UPDATE cases SET helper_id = 'ATT-9' WHERE helper_id = 'HLP-001'"))
    op.execute(sa.text("UPDATE cases SET helper_id = 'ATT-1' WHERE helper_id = 'HLP-002'"))
    op.execute(sa.text("UPDATE users SET user_id = 'ATT-9', display_name = 'Attender Ravi' WHERE user_id = 'HLP-001'"))
    op.execute(sa.text("UPDATE users SET user_id = 'ATT-1', display_name = 'Attender Suresh' WHERE user_id = 'HLP-002'"))

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint("ck_users_role", f"role IN {_BOTH_ROLES}")
    op.execute(sa.text("UPDATE users SET role = 'attender' WHERE role = 'helper'"))
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("ck_users_role", type_="check")
        batch_op.create_check_constraint("ck_users_role", f"role IN {_OLD_ROLES}")

    op.execute(
        sa.text(
            "UPDATE cases SET selected_via = 'attender_confirm' "
            "WHERE selected_via = 'helper_confirm'"
        )
    )
    op.execute(sa.text("UPDATE cases SET gps_source = 'attender_device' WHERE gps_source = 'helper_device'"))

    op.drop_index("ix_cases_helper_id", table_name="cases")
    op.create_index("ix_cases_attender_id", "cases", ["helper_id"])
    with op.batch_alter_table("cases") as batch_op:
        batch_op.alter_column("helper_id", new_column_name="attender_id")
