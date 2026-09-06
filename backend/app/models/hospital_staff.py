"""FR-19 Doctor/Staff Roster + On-Duty Status.

A lightweight, hospital-managed roster — deliberately NOT new `User` rows or a
new `Role` (see the design decision in the project's FR-17..22 expansion
notes): nothing in this phase needs individual doctor/nurse login, the
hospital_receptionist/admin manage this on their behalf, same as a blood-bank
coordinator manages bank stock on behalf of the bank rather than individual
donors. Reversible later via an optional user_id FK if self-service is ever
needed — not built now since nothing calls for it.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class StaffCategory(str, enum.Enum):
    doctor = "doctor"
    nurse = "nurse"
    technician = "technician"
    support = "support"
    admin_staff = "admin_staff"


class OnDutyStatus(str, enum.Enum):
    on_duty = "on_duty"
    off_duty = "off_duty"
    on_leave = "on_leave"


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HospitalStaffMember(Base):
    __tablename__ = "hospital_staff"

    staff_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    hospital_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("hospitals.hospital_id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    staff_category: Mapped[StaffCategory] = mapped_column(
        SAEnum(StaffCategory, native_enum=False, length=16), nullable=False
    )
    specialty: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    on_duty_status: Mapped[OnDutyStatus] = mapped_column(
        SAEnum(OnDutyStatus, native_enum=False, length=10), nullable=False, default=OnDutyStatus.off_duty
    )
    # soft delete — preserves FR-20 attendance history for a removed staff member
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
