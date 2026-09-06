"""FR-20 Staff Attendance / Clock-in-out.

Deliberately separate from FR-19's roster/on-duty concept per the requirement
("a separate, bigger feature than a roster") — this is a time-stamped log, not
just a status flag. Clock-in/out explicitly calls
`hospital_staff.set_on_duty_status` (a service-to-service call, not a DB
trigger — matches the project's "explicit, audited, never inferred"
philosophy already used for FR-16's bed-count changes).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StaffAttendance(Base):
    __tablename__ = "staff_attendance"

    attendance_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    staff_id: Mapped[str] = mapped_column(String(36), ForeignKey("hospital_staff.staff_id"), nullable=False, index=True)
    hospital_id: Mapped[str] = mapped_column(String(32), ForeignKey("hospitals.hospital_id"), nullable=False)
    clock_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    clock_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # free text, no shift-scheduling engine — matches the project's
    # explainable/no-over-engineering ethos elsewhere
    shift_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
