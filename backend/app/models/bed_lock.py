"""FR-3 Bed Lock: temporary exclusive hold on one bed/ICU slot for a case.

Availability is derived: a hospital's available <type> beds =
    hospital.live_<type>_count  -  COUNT(active BedLock rows of that type)
There is no separate "held count" column to drift out of sync.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BedType(str, enum.Enum):
    general = "general"
    ICU = "ICU"


class LockStatus(str, enum.Enum):
    active = "active"
    released = "released"


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BedLock(Base):
    __tablename__ = "bed_locks"

    bed_lock_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    hospital_id: Mapped[str] = mapped_column(String(32), ForeignKey("hospitals.hospital_id"), nullable=False)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), nullable=False)
    bed_type: Mapped[BedType] = mapped_column(
        SAEnum(BedType, native_enum=False, length=10), nullable=False
    )
    lock_status: Mapped[LockStatus] = mapped_column(
        SAEnum(LockStatus, native_enum=False, length=10), nullable=False, default=LockStatus.active
    )
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConflictLog(Base):
    """One row per bed-lock collision — two cases racing for the same last bed.

    Captured here so the conflict is never silently swallowed; a later phase
    wires this into the Control Room alert (FR-10).
    """
    __tablename__ = "conflict_logs"

    conflict_log_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id_a: Mapped[str] = mapped_column(String(36), nullable=False)   # the case that lost the race
    case_id_b: Mapped[str | None] = mapped_column(String(36), nullable=True)  # a case already holding the bed
    hospital_id: Mapped[str] = mapped_column(String(32), nullable=False)
    bed_type: Mapped[BedType] = mapped_column(
        SAEnum(BedType, native_enum=False, length=10), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
