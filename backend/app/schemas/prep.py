"""Pydantic schemas for FR-6 Hospital Pre-Arrival Preparation."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.prep import PrepActionStatus, PrepActionType


class PrepActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prep_action_id: str
    case_id: str
    hospital_id: str
    action_type: PrepActionType
    action_key: str
    label: str
    suggested_department: str | None
    triggered_by_symptom: str | None
    status: PrepActionStatus
    confirmed_by: str | None
    confirmed_at: datetime | None
    created_at: datetime


class PrepActionListOut(BaseModel):
    case_id: str
    pending: list[PrepActionOut]
    confirmed: list[PrepActionOut]


class ConfirmPrepActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receptionist_id: str = Field(min_length=1)
