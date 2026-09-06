"""FR-6 Hospital Pre-Arrival Preparation.

A prep_action only ever reaches status='confirmed' via app.services.prep.confirm()
(the explicit receptionist tap). Nothing else in the codebase writes that value.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PrepActionType(str, enum.Enum):
    baseline = "baseline"
    symptom_based = "symptom_based"


class PrepActionStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PrepAction(Base):
    __tablename__ = "prep_actions"

    prep_action_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), nullable=False)
    hospital_id: Mapped[str] = mapped_column(String(32), nullable=False)

    action_type: Mapped[PrepActionType] = mapped_column(
        SAEnum(PrepActionType, native_enum=False, length=14), nullable=False
    )
    action_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    suggested_department: Mapped[str | None] = mapped_column(String(64), nullable=True)
    triggered_by_symptom: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[PrepActionStatus] = mapped_column(
        SAEnum(PrepActionStatus, native_enum=False, length=12),
        nullable=False,
        default=PrepActionStatus.pending,
    )
    confirmed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
