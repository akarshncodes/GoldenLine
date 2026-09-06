"""FR-22 Rule-Based Fuzzy Import: a parsed-but-not-yet-committed import.

Created by a preview call (CSV upload or Google Sheet fetch), read/edited by
the review UI, consumed by a commit call. Never auto-committed — this row is
the "staging area" between parsing and writing real data.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImportSession(Base):
    __tablename__ = "import_sessions"

    import_session_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    hospital_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("hospitals.hospital_id"), nullable=False, index=True
    )
    target_table: Mapped[str] = mapped_column(String(32), nullable=False)
    # list[dict[str, str]] — every parsed row, keyed by original source column name
    raw_rows: Mapped[list] = mapped_column(JSON, nullable=False)
    # list[{"source_column", "matched_field", "confidence"}] from import_matching.suggest_column_mapping
    suggested_mapping: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
