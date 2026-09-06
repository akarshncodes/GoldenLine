"""Pydantic request/response schemas for FR-0 Case Creation."""
import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.case import CaseStatus, CreationPath, Gender

# 10-digit Indian mobile number.
INDIAN_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")


def _validate_indian_mobile(field_name: str, value: str) -> str:
    if not value or not INDIAN_MOBILE_RE.match(value):
        raise ValueError(
            f"{field_name} must be a valid 10-digit Indian mobile number "
            r"(regex ^[6-9]\d{9}$)"
        )
    return value


class GpsIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timestamp: datetime | None = None


class PatientRequiredIn(BaseModel):
    """Path B: age + gender required, name optional."""
    name: str | None = Field(default=None, max_length=200)
    approx_age: int = Field(ge=0, le=130)
    gender: Gender


class PatientOptionalIn(BaseModel):
    """Path A: everything optional — patient may be unknown at SOS time."""
    name: str | None = Field(default=None, max_length=200)
    approx_age: int | None = Field(default=None, ge=0, le=130)
    gender: Gender | None = None


class PathASosRequest(BaseModel):
    """Path A: family triggers SOS from their phone.

    No helper id here — the helper is auto-assigned from whichever ambulance
    is dispatched (real 108-style dispatch sends driver + helper together, see
    app/services/ambulance.py), not chosen by the family.
    """
    family_phone_number: str
    family_gps: GpsIn = Field(description="Family phone GPS — used ONLY to find the nearest ambulance, never stored as the case location.")
    patient: PatientOptionalIn | None = None
    # FR-12: a verified OTP for family_phone_number is required to create a Path A case.
    otp_verification_id: str = Field(min_length=1)

    @field_validator("family_phone_number")
    @classmethod
    def _check_family_phone(cls, v: str) -> str:
        return _validate_indian_mobile("family_phone_number", v)


class PathBCreateRequest(BaseModel):
    """Path B: the helper starts a case directly on their own device."""
    next_of_kin_phone_number: str
    patient: PatientRequiredIn
    helper_id: str = Field(min_length=1)
    helper_gps: GpsIn = Field(description="Helper device GPS — this becomes the case location.")

    @field_validator("next_of_kin_phone_number")
    @classmethod
    def _check_nok_phone(cls, v: str) -> str:
        return _validate_indian_mobile("next_of_kin_phone_number", v)


class HelperLocationUpdate(BaseModel):
    """Report the helper device location for an existing case (both paths)."""
    helper_id: str = Field(min_length=1)
    gps: GpsIn


class AmbulanceOut(BaseModel):
    id: str
    vehicle_number: str
    driver_name: str
    driver_phone: str
    helper_user_id: str
    base_latitude: float
    base_longitude: float
    distance_km: float


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    creation_path: CreationPath
    status: CaseStatus
    patient_name: str | None
    patient_approx_age: int | None
    patient_gender: Gender | None
    family_phone_number: str | None
    next_of_kin_phone_number: str | None
    gps_latitude: float | None
    gps_longitude: float | None
    gps_timestamp: datetime | None
    gps_source: str | None
    sos_trigger_latitude: float | None
    sos_trigger_longitude: float | None
    sos_trigger_timestamp: datetime | None
    helper_id: str | None
    dispatched_ambulance_id: str | None
    created_at: datetime
    # FR-2
    government_scheme: str | None = None
    selected_hospital_id: str | None = None
    selected_by: str | None = None
    selected_via: str | None = None
    selection_timestamp: datetime | None = None


class CaseSummary(BaseModel):
    """Compact row for the role-scoped case list (GET /cases)."""
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    creation_path: CreationPath
    status: CaseStatus
    patient_name: str | None
    patient_approx_age: int | None
    patient_gender: Gender | None
    helper_id: str | None
    selected_hospital_id: str | None = None
    selected_via: str | None = None
    government_scheme: str | None = None
    created_at: datetime


class SosResponse(BaseModel):
    case: CaseResponse
    dispatched_ambulance: AmbulanceOut | None
    note: str
    # FR-12
    merged_into_existing_case: bool = False
    merge_reason: str | None = None
    rate_limit_flagged: bool = False
