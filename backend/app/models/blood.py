"""FR-5 Blood Check + blood-bank hold requests."""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BloodCheckOutcome(str, enum.Enum):
    hospital_stock_ok = "hospital_stock_ok"
    blood_bank_hold_requested = "blood_bank_hold_requested"


class HoldStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BloodBank(Base):
    """Seeded mock blood banks, each linked to a few hospitals."""
    __tablename__ = "blood_banks"

    blood_bank_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    linked_hospital_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    stock_by_group: Mapped[dict] = mapped_column(JSON, nullable=False)


class BloodCheck(Base):
    """Created ONLY when a bleeding/trauma symptom flag is present (FR-5 rule)."""
    __tablename__ = "blood_checks"

    blood_check_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), unique=True, nullable=False)
    hospital_id: Mapped[str] = mapped_column(String(32), nullable=False)

    blood_requirement_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    blood_group: Mapped[str | None] = mapped_column(String(3), nullable=True)  # if known
    triggered_by_symptoms: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    hospital_stock_sufficient: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hospital_stock_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    outcome: Mapped[BloodCheckOutcome] = mapped_column(
        SAEnum(BloodCheckOutcome, native_enum=False, length=32), nullable=False
    )
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class BloodBankHold(Base):
    """A hold request placed at a blood bank; the coordinator confirms or rejects."""
    __tablename__ = "blood_bank_holds"

    blood_bank_hold_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), nullable=False)
    blood_bank_id: Mapped[str] = mapped_column(String(32), ForeignKey("blood_banks.blood_bank_id"), nullable=False)
    hospital_id: Mapped[str] = mapped_column(String(32), nullable=False)

    blood_group: Mapped[str | None] = mapped_column(String(3), nullable=True)
    units_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    hold_status: Mapped[HoldStatus] = mapped_column(
        SAEnum(HoldStatus, native_enum=False, length=12), nullable=False, default=HoldStatus.pending
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
