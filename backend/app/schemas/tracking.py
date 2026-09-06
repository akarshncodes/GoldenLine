"""Pydantic schemas for FR-9. Only the whitelisted fields are ever serialised."""
from datetime import datetime

from pydantic import BaseModel


class TrackingHospital(BaseModel):
    name: str
    distance_km: float
    rating: float
    cost_tier: str
    why_chosen: str


class TrackingEta(BaseModel):
    min_minutes: int
    max_minutes: int


class PrepUpdate(BaseModel):
    item: str
    status: str


class TrackingPrepStatus(BaseModel):
    total: int
    confirmed: int
    updates: list[PrepUpdate]


class TrackingView(BaseModel):
    status: str  # "active"
    stage: str   # en_route | arrived | discharged
    hospital: TrackingHospital | None
    eta: TrackingEta | None
    bed_lock_status: str
    prep_status: TrackingPrepStatus
    qr_handoff_status: str


class TrackingExpired(BaseModel):
    status: str = "expired"
    message: str = "This link has expired"


class TrackingLinkOut(BaseModel):
    """Only ever shown to someone who already has case access (helper/admin
    console) — this is how they get the token to hand to the family, since
    the SMS itself is a stub. The token alone (not the case) is what the
    public /track/{token} endpoint scopes on.
    """

    token: str
    expires_at: datetime
