"""A hospital's own reported live bed usage.

This is the observed input FR-10 *data reconciliation* compares against the
platform's expectation (active bed locks). It is deliberately a separate table
from `hospitals` (the registry): FR-16 will add the tiered auto-sync — a real
HMS API / a Sheets connector / a one-tap counter — that keeps this fresh. For
now a hospital receptionist posts it via PUT /hospitals/{id}/reported-bed-usage.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class HospitalBedReport(Base):
    __tablename__ = "hospital_bed_reports"

    hospital_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("hospitals.hospital_id"), primary_key=True
    )
    reported_general_in_use: Mapped[int] = mapped_column(Integer, nullable=False)
    reported_icu_in_use: Mapped[int] = mapped_column(Integer, nullable=False)
    reported_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
