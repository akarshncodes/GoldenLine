"""FR-22: `import_sessions` table — staging area for the rule-based fuzzy
import (CSV upload or Google Sheet), between preview and commit.

Final migration of the FR-17..22 HMS expansion.

Revision ID: 0034_fr22_import_sessions
Revises: 0033_fr21_hospital_inventory
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0034_fr22_import_sessions"
down_revision: Union[str, None] = "0033_fr21_hospital_inventory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "import_sessions",
        sa.Column("import_session_id", sa.String(length=36), primary_key=True),
        sa.Column("hospital_id", sa.String(length=32), sa.ForeignKey("hospitals.hospital_id"), nullable=False),
        sa.Column("target_table", sa.String(length=32), nullable=False),
        sa.Column("raw_rows", sa.JSON(), nullable=False),
        sa.Column("suggested_mapping", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_import_sessions_hospital_id", "import_sessions", ["hospital_id"])


def downgrade() -> None:
    op.drop_index("ix_import_sessions_hospital_id", table_name="import_sessions")
    op.drop_table("import_sessions")
