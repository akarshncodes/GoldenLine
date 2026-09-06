"""Pydantic schemas for FR-3 Bed Lock."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.bed_lock import BedType, LockStatus


class BedLockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bed_lock_id: str
    hospital_id: str
    case_id: str
    bed_type: BedType
    lock_status: LockStatus
    locked_at: datetime
    released_at: datetime | None


class ConflictLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conflict_log_id: str
    case_id_a: str
    case_id_b: str | None
    hospital_id: str
    bed_type: BedType
    detected_at: datetime


class ActiveLockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    bed_type: BedType
    locked_at: datetime


class HospitalDashboardRow(BaseModel):
    hospital_id: str
    name: str
    total_general_beds: int
    active_general_locks: int
    reserved_general_beds: int
    available_general_beds: int
    total_icu_beds: int
    active_icu_locks: int
    reserved_icu_beds: int
    available_icu_beds: int
    locked_for_cases: list[ActiveLockOut]


class ReleaseResponse(BaseModel):
    released_lock: BedLockOut
    hospital_id: str
    bed_type: BedType
    available_general_beds: int
    available_icu_beds: int
    case_selection_cleared: bool
