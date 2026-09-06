"""FR-16 Hospital Data Sync — audit trail of every bed-count change.

One row per change, whichever tier (or the QR-handoff auto-decrement) caused it.
Requirement: the auto-decrement on a confirmed admission must be *traceable to
that exact handoff event* — `source='qr_handoff_admission'` rows carry both
`related_case_id` and `related_handoff_token_id`.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class HospitalSyncEvent(Base):
    __tablename__ = "hospital_sync_events"

    sync_event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    hospital_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("hospitals.hospital_id"), nullable=False, index=True
    )
    # one of: hms_api | google_sheets | manual_counter | qr_handoff_admission |
    #         discharge_bed_released
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    bed_type: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 'general'|'ICU'|None

    general_before: Mapped[int] = mapped_column(Integer, nullable=False)
    general_after: Mapped[int] = mapped_column(Integer, nullable=False)
    icu_before: Mapped[int] = mapped_column(Integer, nullable=False)
    icu_after: Mapped[int] = mapped_column(Integer, nullable=False)

    # set only for source='qr_handoff_admission' (FR-7 tie-in)
    related_case_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    related_handoff_token_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # set only for source='walkin_admission'/'walkin_discharge' (FR-18 tie-in)
    related_patient_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    actor: Mapped[str | None] = mapped_column(String(64), nullable=True)  # user_id / 'system'
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
