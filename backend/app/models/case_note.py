"""FR-1 refinement (2026-09-05): follow-up case notes.

The Assessment's own `raw_voice_transcript` is the one-time initial-triage
note. This is the separate, append-only channel for updates a helper adds
*during* the case ("family says patient just vomited blood") — never
overwrites anything, never itself changes the saved symptom_checklist /
criticality_level (those stay the reviewed-once, structured, FR-1-safe
fields). Helper-authored only, by design — not a two-way chat.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaseNote(Base):
    __tablename__ = "case_notes"

    case_note_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), nullable=False)
    author_id: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # [{"symptom": "...", "keyword": "..."}, ...] — same shape/purpose as the
    # voice-derivation step's matched_keywords (assessment.py), computed once
    # at creation and stored so the display never has to re-derive it.
    matched_keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
