"""Pydantic schemas for FR-10 Control Room."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.control_room import FlagStatus, FlagType


class FlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    flag_id: str
    flag_type: FlagType
    related_case_ids: list[str]
    related_hospital_id: str | None
    details: str
    status: FlagStatus
    escalated_to: str
    escalated_at: datetime
    created_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None
    resolution_note: str | None


class ScanResultOut(BaseModel):
    anomaly_flag_ids: list[str]
    conflict_flag_ids: list[str]
    reconciliation_flag_ids: list[str]
    total: int


class ResolveFlagRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resolution_note: str | None = Field(default=None, max_length=1000)


class ReportedBedUsageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reported_general_in_use: int = Field(ge=0)
    reported_icu_in_use: int = Field(ge=0)


class ReportedBedUsageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hospital_id: str
    reported_general_in_use: int
    reported_icu_in_use: int
    reported_by: str | None
    reported_at: datetime
