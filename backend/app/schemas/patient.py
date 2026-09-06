"""Pydantic schemas for FR-18 Patient Census + manual admit/discharge."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.case import Gender
from app.models.patient import BedAssignmentStatus, PatientStatus, PatientType


class PatientCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=200)
    approx_age: int | None = Field(default=None, ge=0, le=150)
    gender: Gender | None = None
    phone_number: str | None = Field(default=None, pattern=r"^[6-9]\d{9}$")
    # 'emergency_case' is reserved for the internal QR-handoff census hook —
    # never settable from this endpoint.
    patient_type: Literal["walk_in", "scheduled"] = "walk_in"


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    hospital_id: str
    full_name: str
    approx_age: int | None
    gender: Gender | None
    phone_number: str | None
    patient_type: PatientType
    linked_case_id: str | None
    status: PatientStatus
    created_at: datetime
    created_by: str | None


class BedAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bed_assignment_id: str
    patient_id: str
    hospital_id: str
    category_code: str
    bed_label: str | None
    status: BedAssignmentStatus
    assigned_at: datetime
    released_at: datetime | None
    assigned_by: str | None
    released_by: str | None


class AdmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_code: str = Field(min_length=1, max_length=32)
    bed_label: str | None = Field(default=None, max_length=50)
