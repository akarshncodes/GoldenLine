"""FR-8 Discharge Feedback — one structured-tags-only submission per case.

`case_feedback.case_id` carries a real DB UNIQUE constraint: a second submission
is rejected by the database, not by an application if-check.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReadyAsShownTag(str, enum.Enum):
    yes = "yes"
    no = "no"
    somewhat = "somewhat"


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FeedbackInvite(Base):
    """The link (mock SMS) sent to the family / next-of-kin after discharge."""
    __tablename__ = "feedback_invites"

    invite_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.case_id"), unique=True, nullable=False
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    link: Mapped[str] = mapped_column(String(300), nullable=False)
    recipient_phone: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sms_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class CaseFeedback(Base):
    """Structured tags only — no freeform text field anywhere."""
    __tablename__ = "case_feedback"

    feedback_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    # DB-level one-per-case guarantee (FR-8 rule).
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.case_id"), unique=True, nullable=False
    )
    hospital_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # for the future reliability score

    wait_time_tag: Mapped[int] = mapped_column(Integer, nullable=False)       # 1-5
    staff_behavior_tag: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    cleanliness_tag: Mapped[int] = mapped_column(Integer, nullable=False)     # 1-5
    billing_tag: Mapped[int] = mapped_column(Integer, nullable=False)        # 1-5
    ready_as_shown_tag: Mapped[ReadyAsShownTag] = mapped_column(
        SAEnum(ReadyAsShownTag, native_enum=False, length=10), nullable=False
    )

    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
