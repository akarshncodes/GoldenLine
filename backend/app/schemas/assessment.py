"""Pydantic schemas for FR-1 On-Scene Assessment.

`extra="forbid"` on every request model is deliberate: it hard-blocks any
attempt to smuggle in a free-text "diagnosis" field (FRP FR-1 safety rule).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import SUPPORTED_LANGUAGES
from app.models.assessment import CriticalityLevel, InputMethod, SymptomTag


class ChecklistSubmission(BaseModel):
    """Tap method: the helper ticks boxes directly."""
    model_config = ConfigDict(extra="forbid")

    criticality_level: CriticalityLevel
    symptom_checklist: list[SymptomTag] = Field(min_length=1)
    confirm: bool = Field(description="Must be true — the mandatory explicit confirm step.")

    @field_validator("confirm")
    @classmethod
    def _must_confirm(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("assessment is only saved when confirm=true")
        return v

    @field_validator("symptom_checklist")
    @classmethod
    def _dedupe(cls, v: list[SymptomTag]) -> list[SymptomTag]:
        return list(dict.fromkeys(v))


class VoiceTranscribeRequest(BaseModel):
    """Voice method step 1: submit a transcript, get a derived checklist back (not saved)."""
    model_config = ConfigDict(extra="forbid")

    transcript: str = Field(min_length=1)
    language_code: str

    @field_validator("language_code")
    @classmethod
    def _supported_language(cls, v: str) -> str:
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"language_code '{v}' is not supported. "
                f"Supported: {sorted(SUPPORTED_LANGUAGES)}"
            )
        return v


class MatchedKeywordOut(BaseModel):
    """One (symptom, keyword) pair the transcript literally matched — shown to
    the helper so they can see *why* something was derived, never used to
    silently change what gets saved."""
    symptom: SymptomTag
    keyword: str


class DerivedChecklistResponse(BaseModel):
    """What the voice step returns — a proposal the helper must review + confirm."""
    case_id: str
    criticality_level: CriticalityLevel | None
    symptom_checklist: list[SymptomTag]
    matched_keywords: list[MatchedKeywordOut] = []
    raw_voice_transcript: str
    saved: bool = False
    note: str = (
        "Not saved. Review these fields and POST them to "
        "/cases/{case_id}/assessment/confirm with confirm=true to persist."
    )


class ConfirmAssessmentRequest(BaseModel):
    """Voice method step 2: persist the reviewed checklist."""
    model_config = ConfigDict(extra="forbid")

    criticality_level: CriticalityLevel
    symptom_checklist: list[SymptomTag] = Field(min_length=1)
    raw_voice_transcript: str = Field(min_length=1)
    confirm: bool

    @field_validator("confirm")
    @classmethod
    def _must_confirm(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("assessment is only saved when confirm=true")
        return v

    @field_validator("symptom_checklist")
    @classmethod
    def _dedupe(cls, v: list[SymptomTag]) -> list[SymptomTag]:
        return list(dict.fromkeys(v))


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: str
    case_id: str
    criticality_level: CriticalityLevel
    symptom_checklist: list[SymptomTag]
    input_method: InputMethod
    raw_voice_transcript: str | None
    created_at: datetime
    updated_at: datetime
