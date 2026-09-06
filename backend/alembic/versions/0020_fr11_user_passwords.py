"""FR-11 / NFR 7.1: staff accounts get a hashed password (never plain text)

Adds `users.password_hash` and backfills the seeded demo accounts with a
PBKDF2-HMAC-SHA256 hash of their documented dev password (`"<user_id>.sih2026"`).
The hash format matches `app.services.security` exactly — a parity test verifies
`security.verify_password` accepts these hashes.

Revision ID: 0020_fr11_user_passwords
Revises: 0019_fr16_hospital_sync
Create Date: 2026-09-04
"""
import base64
import hashlib
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0020_fr11_user_passwords"
down_revision: Union[str, None] = "0019_fr16_hospital_sync"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Seeded account ids (mirrors app/services/user_seed.py SEED_USERS; guarded by
# tests/test_fr4_fr5_seed_parity.py::test_migration_0016_users_match_seed).
_SEED_USER_IDS = [
    "admin", "control-room", "ATT-9", "ATT-1",
    "recep-hosp-001", "recep-hosp-004", "recep-hosp-007",
    "coord-bb-01", "coord-bb-02",
]
_DEV_PASSWORD_SUFFIX = "sih2026"          # mirrors user_seed._DEV_PASSWORD_SUFFIX
_PBKDF2_ALGO = "pbkdf2_sha256"            # mirrors security._PBKDF2_ALGO
_PBKDF2_ITERATIONS = 480_000             # mirrors security._PBKDF2_ITERATIONS


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _hash(plain: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}${_b64url(salt)}${_b64url(digest)}"


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))

    for uid in _SEED_USER_IDS:
        op.execute(
            sa.text("UPDATE users SET password_hash = :h WHERE user_id = :u").bindparams(
                h=_hash(f"{uid}.{_DEV_PASSWORD_SUFFIX}"), u=uid
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_hash")
