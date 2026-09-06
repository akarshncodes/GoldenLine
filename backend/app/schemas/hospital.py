"""Pydantic schemas for FR-2 AI Hospital Ranking + final selection."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.hospital import HospitalSyncTier
from app.schemas.bed_lock import BedLockOut
from app.services.hospital_ranking import GOVERNMENT_SCHEMES


class HospitalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hospital_id: str
    name: str
    specialties: list[str]
    live_bed_count: int
    live_icu_count: int
    bed_count_by_type: dict[str, int]
    distance_km: float
    eta_minutes: int
    rating: float
    cost_tier: str
    accepted_schemes: list[str]
    latitude: float | None = None
    longitude: float | None = None
    # FR-16
    hospital_sync_tier: HospitalSyncTier
    last_synced_at: datetime | None = None


class RankedHospitalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    hospital_id: str
    name: str
    cost_tier: str
    rank: int
    score: float
    accepts_case_scheme: bool
    scheme_boost_applied: bool
    distance_km: float
    eta_minutes: int
    rating: float
    live_bed_count: int
    live_icu_count: int
    reason: str
    available_general_beds: int | None = None
    available_icu_beds: int | None = None
    latitude: float | None = None
    longitude: float | None = None


class RankingResponse(BaseModel):
    case_id: str
    creation_path: str
    case_scheme: str | None
    required_specialties: list[str]
    bed_type_needed: str | None
    excluded_hospital_ids: list[str]
    excluded_no_capacity_ids: list[str]
    explanation: str
    ranked: list[RankedHospitalOut]
    # "live" once the helper's device has reported the case's actual location
    # at least once — every distance/ETA above is real haversine distance from
    # that point. "estimated" = still using each hospital's fixed mock distance.
    distance_source: str
    # The helper's actual choice screen: one best-by-bed/distance/ETA hospital
    # per cost class (economical/moderate/expensive), or null where no capable
    # hospital exists in that class. See services/hospital_ranking.best_in_class.
    classes: dict[str, RankedHospitalOut | None]


class SchemeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    government_scheme: str | None = Field(
        description=f"One of {sorted(GOVERNMENT_SCHEMES)}, or null to clear."
    )

    @field_validator("government_scheme")
    @classmethod
    def _known_scheme(cls, v: str | None) -> str | None:
        if v is not None and v not in GOVERNMENT_SCHEMES:
            raise ValueError(
                f"government_scheme must be one of {sorted(GOVERNMENT_SCHEMES)} or null"
            )
        return v


class HospitalSelectionRequest(BaseModel):
    """Both paths: the helper explicitly taps one of the 3 cost-class hospitals
    shown for this case (see RankingResponse.classes) — after asking the family
    inside the ambulance which class they'd like. Never the family, never
    auto-selected, and never any hospital outside those 3 class picks."""
    model_config = ConfigDict(extra="forbid")

    hospital_id: str = Field(min_length=1)
    helper_id: str = Field(min_length=1)


class SelectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    creation_path: str
    selected_hospital_id: str | None
    selected_by: str | None
    selected_via: str | None
    selection_timestamp: datetime | None
    bed_lock: BedLockOut | None = None
