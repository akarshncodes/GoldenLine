"""Pydantic schemas for FR-19 Doctor/Staff Roster."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.hospital_staff import OnDutyStatus, StaffCategory


class StaffCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)
    staff_category: StaffCategory
    specialty: str | None = Field(default=None, max_length=100)
    phone_number: str | None = Field(default=None, pattern=r"^[6-9]\d{9}$")


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    staff_id: str
    hospital_id: str
    full_name: str
    staff_category: StaffCategory
    specialty: str | None
    phone_number: str | None
    on_duty_status: OnDutyStatus
    is_active: bool
    created_at: datetime
    created_by: str | None


class OnDutyStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    on_duty_status: OnDutyStatus
