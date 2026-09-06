"""FR-17 Bed/Room Categories.

Additive to FR-2/FR-3/FR-16's `Hospital.live_bed_count`/`live_icu_count` —
this table never duplicates or replaces those two columns, it only adds
categories the emergency pipeline never routes into (private, ward, isolation,
etc). See app/models/hospital.py for the general/ICU capacity columns.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BedCategory(Base):
    """A hospital-defined room/bed category beyond general+ICU, e.g. 'private'."""
    __tablename__ = "bed_categories"
    __table_args__ = (UniqueConstraint("hospital_id", "category_code", name="uq_bed_category_hospital_code"),)

    bed_category_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hospital_id: Mapped[str] = mapped_column(String(32), ForeignKey("hospitals.hospital_id"), nullable=False)
    category_code: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    total_beds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
