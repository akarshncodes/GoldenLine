"""Pydantic schemas for FR-7 QR Handoff."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class QrPayloadOut(BaseModel):
    """Exactly what the helper's app renders into a QR — no patient data."""
    case_id: str
    token: str
    expires_at: datetime
    qr_payload: str  # compact string form the QR encodes


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    token: str = Field(min_length=1)
    scanned_by: str = Field(min_length=1)


class ClinicalInfoUpdate(BaseModel):
    """Admission-ready data the helper records during transit."""
    model_config = ConfigDict(extra="forbid")

    patient_name: str | None = Field(default=None, max_length=200)
    known_allergies: str | None = Field(default=None, max_length=1000)
    current_medications: str | None = Field(default=None, max_length=1000)
    blood_group: str | None = Field(default=None, max_length=3)
