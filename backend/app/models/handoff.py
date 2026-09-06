"""FR-7 QR Handoff at Arrival — short-lived verification tokens.

The QR the helper shows encodes only {case_id, token} — never patient data.
A scan must present a token that is for the right case, not expired, not used.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QrHandoffToken(Base):
    __tablename__ = "qr_handoff_tokens"

    token_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
