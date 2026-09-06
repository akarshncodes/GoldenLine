"""Pydantic schemas for FR-16 Hospital Data Sync."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.hospital import HospitalSyncTier


class SyncEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sync_event_id: str
    hospital_id: str
    source: str
    bed_type: str | None
    general_before: int
    general_after: int
    icu_before: int
    icu_after: int
    related_case_id: str | None
    related_handoff_token_id: str | None
    actor: str | None
    note: str
    created_at: datetime


class SyncOutcomeOut(BaseModel):
    hospital_id: str
    source: str
    bed_count_by_type: dict[str, int]
    last_synced_at: datetime
    event: SyncEventOut


class SheetSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # optional: if omitted, the hospital's stored sheet_url is used
    sheet_url: str | None = Field(default=None, max_length=500)


class ManualAdjustRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bed_type: Literal["general", "ICU"]
    delta: Literal[-1, 1]


class SyncTierUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hospital_sync_tier: HospitalSyncTier
    sheet_url: str | None = Field(default=None, max_length=500)


class SyncStatusOut(BaseModel):
    hospital_id: str
    hospital_sync_tier: HospitalSyncTier
    sheet_url: str | None
    bed_count_by_type: dict[str, int]
    last_synced_at: datetime | None
    recent_events: list[SyncEventOut]
