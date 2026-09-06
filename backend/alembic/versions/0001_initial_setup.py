"""initial setup - infra only (no FR feature tables)

Creates a small key/value table used to record schema/bootstrap metadata.
Feature tables (hospitals, beds, cases, attenders, reliability, feedback)
are added in later phases.

Revision ID: 0001_initial_setup
Revises:
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_setup"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_meta",
        sa.Column("key", sa.String(length=100), primary_key=True),
        sa.Column("value", sa.String(length=500), nullable=False),
    )
    op.bulk_insert(
        sa.table(
            "app_meta",
            sa.column("key", sa.String),
            sa.column("value", sa.String),
        ),
        [{"key": "schema_phase", "value": "0"}],
    )


def downgrade() -> None:
    op.drop_table("app_meta")
