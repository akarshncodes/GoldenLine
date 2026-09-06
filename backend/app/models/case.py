"""FR-0 Case Creation — the single Case model shared by both creation paths.

One table, `cases`, with a `creation_path` discriminator ('A' or 'B').
There are intentionally NOT two separate tables.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CreationPath(str, enum.Enum):
    A = "A"  # family-triggered SOS
    B = "B"  # helper-started case


class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"
    unknown = "unknown"


class CaseStatus(str, enum.Enum):
    SOS_TRIGGERED = "SOS_TRIGGERED"
    AMBULANCE_DISPATCHED = "AMBULANCE_DISPATCHED"
    OPEN = "OPEN"
    ADMITTED = "ADMITTED"       # FR-7: valid QR handoff scanned at the hospital
    DISCHARGED = "DISCHARGED"   # FR-8: discharge triggered


class AmbulanceLevel(str, enum.Enum):
    BLS = "BLS"  # Basic Life Support
    ALS = "ALS"  # Advanced Life Support


def _new_case_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_case_id)
    creation_path: Mapped[CreationPath] = mapped_column(
        SAEnum(CreationPath, native_enum=False, length=1), nullable=False
    )

    # --- patient basic details (name optional; age/gender required only on Path B) ---
    patient_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    patient_approx_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patient_gender: Mapped[Gender | None] = mapped_column(
        SAEnum(Gender, native_enum=False, length=10), nullable=True
    )

    # --- contact number: exactly one of these is set, depending on the path ---
    family_phone_number: Mapped[str | None] = mapped_column(String(10), nullable=True)      # Path A
    next_of_kin_phone_number: Mapped[str | None] = mapped_column(String(10), nullable=True)  # Path B

    # --- authoritative case location ---
    # FR-0 item 4: this ALWAYS comes from the HELPER's device once an ambulance
    # is involved, never the family's phone. On a fresh Path A case it is set the
    # instant the ambulance (and its helper) is auto-dispatched; Path B sets it
    # immediately from the helper's own device at case creation.
    gps_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gps_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # only ever 'helper_device'

    # --- Path A SOS trigger coordinates (AUDIT ONLY) ---
    # FR-0 line 97: the family SOS location is "attached" to the case. But per
    # line 85 it is NOT the authoritative case location — it is only what the
    # family's phone reported at SOS time and what was used to find an ambulance.
    # Never read these for routing/hospital logic; use gps_latitude/longitude.
    sos_trigger_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    sos_trigger_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    sos_trigger_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # The helper who rides with the ambulance (not the driver). Path A: auto-set
    # from the dispatched ambulance's fixed helper the instant the ambulance is
    # assigned — real 108-style dispatch sends both people together, so there is
    # no separate "claim this case" step. Path B: set from the helper's own login.
    helper_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- mock ambulance dispatch (Path A) ---
    # No real ambulance registry/tracking yet: this is the id of a hardcoded fake.
    dispatched_ambulance_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, native_enum=False, length=32), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    # --- FR-2: government scheme indication + final hospital selection ---
    # scheme code the family/helper indicated (e.g. 'ayushman_bharat'); None if not indicated
    government_scheme: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # set ONLY by an explicit helper tap, on one of the 3 cost-class hospitals
    # shown for that case (both paths) — never auto-selected, never by family.
    selected_hospital_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    selected_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selected_via: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'helper_confirm'
    selection_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- FR-4: ambulance capability level (default BLS for test data) ---
    ambulance_level: Mapped[AmbulanceLevel] = mapped_column(
        SAEnum(AmbulanceLevel, native_enum=False, length=3),
        nullable=False,
        default=AmbulanceLevel.BLS,
        server_default=AmbulanceLevel.BLS.value,
    )

    # --- FR-7: admission-ready clinical info, captured during transit ---
    known_allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_medications: Mapped[str | None] = mapped_column(Text, nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # --- FR-7: confirmed admission (valid QR scan at the hospital) ---
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admitted_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # --- FR-8: discharge ---
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- FR-11: Path A family account this case belongs to (for role scoping) ---
    family_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
