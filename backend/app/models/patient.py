"""FR-18 Patient Census: hospital-wide patient tracking, independent of the
emergency case pipeline (FR-0..FR-16) — but every emergency-admitted case gets
its own visibility-only entry here too (patient_type='emergency_case'), so this
table reflects EVERY patient in the hospital, not just walk-ins. See
app/services/patients.py.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.case import Gender


class PatientType(str, enum.Enum):
    walk_in = "walk_in"
    scheduled = "scheduled"
    emergency_case = "emergency_case"


class PatientStatus(str, enum.Enum):
    waiting = "waiting"
    admitted = "admitted"
    discharged = "discharged"
    cancelled = "cancelled"


class BedAssignmentStatus(str, enum.Enum):
    active = "active"
    released = "released"


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    hospital_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("hospitals.hospital_id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    approx_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[Gender | None] = mapped_column(SAEnum(Gender, native_enum=False, length=10), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    patient_type: Mapped[PatientType] = mapped_column(
        SAEnum(PatientType, native_enum=False, length=16), nullable=False
    )
    # set only for patient_type='emergency_case' — links back to the originating case
    linked_case_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("cases.case_id"), nullable=True, index=True)
    status: Mapped[PatientStatus] = mapped_column(
        SAEnum(PatientStatus, native_enum=False, length=12), nullable=False, default=PatientStatus.waiting
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class BedAssignment(Base):
    """One active bed hold per patient at a time — enforced in the service layer.

    category_code is either 'general'/'ICU' (the FR-2/FR-3 columns — admitting
    into these atomically decrements Hospital.live_bed_count/live_icu_count, see
    hospital_sync.record_walkin_admission_decrement) or an FR-17 bed_categories
    code (purely local, no interaction with the emergency pipeline).
    """
    __tablename__ = "bed_assignments"

    bed_assignment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.patient_id"), nullable=False, index=True)
    hospital_id: Mapped[str] = mapped_column(String(32), ForeignKey("hospitals.hospital_id"), nullable=False)
    category_code: Mapped[str] = mapped_column(String(32), nullable=False)
    bed_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[BedAssignmentStatus] = mapped_column(
        SAEnum(BedAssignmentStatus, native_enum=False, length=10), nullable=False, default=BedAssignmentStatus.active
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    released_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
