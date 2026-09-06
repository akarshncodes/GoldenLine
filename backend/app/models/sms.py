"""Shared outbound-SMS log — the one messaging system (FR-8, FR-9, later FR-11).

A real gateway plugs into app/services/sms.py::send_sms without callers changing.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SmsCategory(str, enum.Enum):
    tracking_link = "tracking_link"            # FR-9
    discharge_feedback = "discharge_feedback"  # FR-8
    otp = "otp"                               # FR-12
    critical_update = "critical_update"        # FR-13 (SMS fallback when data is down)
    password_reset = "password_reset"          # FR-11 (staff forgot-password code)


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    sms_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    to_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[SmsCategory] = mapped_column(
        SAEnum(SmsCategory, native_enum=False, length=32), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    case_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="stub")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
