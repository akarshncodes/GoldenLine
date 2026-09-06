"""FR-9 Family Access via SMS Link — one unguessable tracking token per Path B case."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CaseTrackingToken(Base):
    __tablename__ = "case_tracking_tokens"

    tracking_token_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    # 1:1 with the case.
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.case_id"), unique=True, nullable=False
    )
    # long, random, NOT the case_id. This is the "password" for the tracking page.
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    token_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    # placeholder far-future value at creation; recomputed to (closure + 24-48h)
    # once the case is discharged.
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
