"""Pydantic schemas for FR-8 Discharge Feedback. Structured tags ONLY — no free text."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.feedback import ReadyAsShownTag

Stars = Field(ge=1, le=5, description="1 (worst) - 5 (best)")


class FeedbackInviteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invite_id: str
    case_id: str
    link: str
    recipient_phone: str | None
    sms_sent_at: datetime


class FeedbackSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")  # blocks any freeform text field

    token: str = Field(min_length=1)
    wait_time_tag: int = Stars
    staff_behavior_tag: int = Stars
    cleanliness_tag: int = Stars
    billing_tag: int = Stars
    ready_as_shown_tag: ReadyAsShownTag


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    feedback_id: str
    case_id: str
    hospital_id: str | None
    wait_time_tag: int
    staff_behavior_tag: int
    cleanliness_tag: int
    billing_tag: int
    ready_as_shown_tag: ReadyAsShownTag
    submitted_at: datetime
