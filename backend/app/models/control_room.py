"""FR-10 Control Room (Background Supervisor) — internal alert flags.

The Control Room never talks to families or hospitals. It watches the data the
rest of the pipeline already produces (case/ambulance status, Phase-4's
`conflict_logs`, hospital bed counts) and raises a `Flag` to a human whenever
something looks wrong.

Two hard rules encoded here:
  * A Flag is ALWAYS born `escalated`, with a human `escalated_to` contact set.
    There is no code path that creates a Flag `open` or `resolved`.
  * The system NEVER marks a Flag `resolved`. Only
    `app.services.control_room.resolve_flag()` — the explicit human-resolve
    endpoint — assigns `status='resolved'`. `tests/test_fr10_control_room.py`
    regex-scans `app/` to enforce that.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FlagType(str, enum.Enum):
    anomaly = "anomaly"
    conflict = "conflict"
    reconciliation = "reconciliation"


class FlagStatus(str, enum.Enum):
    open = "open"            # defined by the FRP data model; our code never emits it
    escalated = "escalated"  # every flag starts here
    resolved = "resolved"    # only reachable via resolve_flag() (human action)


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    # naive UTC — matches app.models.auth so cross-table datetime comparisons on
    # SQLite don't mix aware/naive values (see project-overview gotcha #1).
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Flag(Base):
    __tablename__ = "flags"

    flag_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    flag_type: Mapped[FlagType] = mapped_column(
        SAEnum(FlagType, native_enum=False, length=16), nullable=False
    )

    # "related_case_id(s)" — a list so a conflict flag can name both racing cases.
    related_case_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    related_hospital_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

    details: Mapped[str] = mapped_column(Text, nullable=False)

    # Re-run idempotency guard for the scan job (not a user-facing field).
    dedup_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)

    status: Mapped[FlagStatus] = mapped_column(
        SAEnum(FlagStatus, native_enum=False, length=12),
        nullable=False,
        default=FlagStatus.escalated,
    )
    escalated_to: Mapped[str] = mapped_column(String(200), nullable=False)
    escalated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)   # human user_id
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
