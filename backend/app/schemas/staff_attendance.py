"""Pydantic schemas for FR-20 Staff Attendance / Clock-in-out."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClockInRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shift_label: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=1000)


class AttendanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attendance_id: str
    staff_id: str
    hospital_id: str
    clock_in_at: datetime
    clock_out_at: datetime | None
    shift_label: str | None
    recorded_by: str | None
    notes: str | None
