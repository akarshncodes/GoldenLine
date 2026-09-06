"""Pydantic schemas for FR-17 Bed/Room Categories."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BedCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bed_category_id: int
    hospital_id: str
    category_code: str
    label: str
    total_beds: int
    created_at: datetime
    updated_at: datetime


class BedCategoryUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=100)
    total_beds: int = Field(ge=0)


class CapacitySnapshot(BaseModel):
    """Merges FR-2/FR-3's general+ICU columns with FR-17's extra categories."""
    model_config = ConfigDict(extra="forbid")

    hospital_id: str
    general_total: int
    icu_total: int
    categories: list[BedCategoryOut]
