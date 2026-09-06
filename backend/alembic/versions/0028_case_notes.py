"""FR-1 refinement: `case_notes` table for follow-up helper notes.

Separate from the Assessment's own `raw_voice_transcript` (the one-time
initial-triage note) — this is an append-only log of updates a helper adds
during a case, each with its own matched-keyword highlights precomputed at
creation time.

Revision ID: 0028_case_notes
Revises: 0027_route_path
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0028_case_notes"
down_revision: Union[str, None] = "0027_route_path"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "case_notes",
        sa.Column("case_note_id", sa.String(length=36), primary_key=True),
        sa.Column("case_id", sa.String(length=36), sa.ForeignKey("cases.case_id"), nullable=False),
        sa.Column("author_id", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("matched_keywords", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_case_notes_case_id", "case_notes", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_case_notes_case_id", table_name="case_notes")
    op.drop_table("case_notes")
