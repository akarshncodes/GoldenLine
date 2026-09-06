"""FR-1 On-Scene Assessment — one symptom log per case.

Safety rule (FRP FR-1): there is NO free-text diagnosis anywhere. Only a fixed
criticality enum and a fixed set of observable symptom tags.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Store the enum *value* (e.g. 'Critical'), not its name (e.g. 'CRITICAL')."""
    return [member.value for member in enum_cls]


class CriticalityLevel(str, enum.Enum):
    CRITICAL = "Critical"
    SERIOUS = "Serious"
    STABLE = "Stable"


class InputMethod(str, enum.Enum):
    checklist = "checklist"
    voice = "voice"


class SymptomTag(str, enum.Enum):
    """Fixed starter list of observable symptoms (no diagnoses)."""
    chest_pain = "chest_pain"
    breathing_difficulty = "breathing_difficulty"
    visible_bleeding = "visible_bleeding"
    trauma = "trauma"
    unconsciousness = "unconsciousness"
    seizure = "seizure"
    severe_pain = "severe_pain"
    burns = "burns"
    pregnancy_labour = "pregnancy_labour"
    stroke_signs = "stroke_signs"
    high_fever = "high_fever"
    vomiting = "vomiting"
    allergic_reaction = "allergic_reaction"
    poisoning = "poisoning"


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Assessment(Base):
    __tablename__ = "assessments"

    assessment_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    # 1:1 with a case created in FR-0.
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.case_id"), unique=True, nullable=False
    )

    criticality_level: Mapped[CriticalityLevel] = mapped_column(
        SAEnum(
            CriticalityLevel,
            native_enum=False,
            length=16,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    # list of SymptomTag values, stored as a JSON array of strings
    symptom_checklist: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    input_method: Mapped[InputMethod] = mapped_column(
        SAEnum(
            InputMethod,
            native_enum=False,
            length=16,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    # kept for audit even after the checklist has been derived from it
    raw_voice_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
