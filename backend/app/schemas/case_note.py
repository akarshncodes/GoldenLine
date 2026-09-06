"""Pydantic schemas for FR-1's follow-up case-notes channel (2026-09-05)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assessment import MatchedKeywordOut


class CaseNoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    author_id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class CaseNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_note_id: str
    case_id: str
    author_id: str
    text: str
    matched_keywords: list[MatchedKeywordOut]
    created_at: datetime
