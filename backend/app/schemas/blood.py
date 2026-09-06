"""Pydantic schemas for FR-5 Blood Check."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.blood import BloodCheckOutcome, HoldStatus


class BloodBankOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    blood_bank_id: str
    name: str
    latitude: float
    longitude: float
    linked_hospital_ids: list[str]
    stock_by_group: dict


class BloodCheckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    blood_check_id: str
    case_id: str
    hospital_id: str
    blood_requirement_flag: bool
    blood_group: str | None
    triggered_by_symptoms: list[str]
    hospital_stock_sufficient: bool
    hospital_stock_snapshot: dict
    outcome: BloodCheckOutcome
    checked_at: datetime


class BloodBankHoldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    blood_bank_hold_id: str
    case_id: str
    blood_bank_id: str
    hospital_id: str
    blood_group: str | None
    units_requested: int
    hold_status: HoldStatus
    requested_at: datetime
    decided_at: datetime | None
    decided_by: str | None


class HoldDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coordinator_id: str = Field(min_length=1)
