"""Fix: HLP-001 and HLP-002 (renamed from ATT-9/ATT-1 by migration 0023) never
had their password re-hashed for the new id — they were left authenticating
with the OLD pre-rename password (`ATT-9.sih2026` / `ATT-1.sih2026`) instead
of the documented `<user_id>.sih2026` convention. 0023 only re-hashed the
brand-new helper rows it inserted (HLP-003/004/005), not the two it renamed
in place. Every other helper (HLP-003..020) was a fresh insert with a correct
hash from the start, so this only ever affected these 2 accounts.

Revision ID: 0026_fix_hlp001_hlp002_passwords
Revises: 0025_dindigul_waypoints
Create Date: 2026-09-05
"""
import base64
import hashlib
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0026_fix_hlp001_hlp002_passwords"
down_revision: Union[str, None] = "0025_dindigul_waypoints"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_AFFECTED = ["HLP-001", "HLP-002"]
_OLD_IDS = {"HLP-001": "ATT-9", "HLP-002": "ATT-1"}
_DEV_PASSWORD_SUFFIX = "sih2026"
_PBKDF2_ALGO = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 480_000


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _hash(plain: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}${_b64url(salt)}${_b64url(digest)}"


def upgrade() -> None:
    for uid in _AFFECTED:
        op.execute(
            sa.text("UPDATE users SET password_hash = :h WHERE user_id = :u").bindparams(
                h=_hash(f"{uid}.{_DEV_PASSWORD_SUFFIX}"), u=uid
            )
        )


def downgrade() -> None:
    for uid, old_id in _OLD_IDS.items():
        op.execute(
            sa.text("UPDATE users SET password_hash = :h WHERE user_id = :u").bindparams(
                h=_hash(f"{old_id}.{_DEV_PASSWORD_SUFFIX}"), u=uid
            )
        )
