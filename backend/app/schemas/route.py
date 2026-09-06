"""Pydantic schemas for FR-4 Route / Traffic / Waypoint."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.case import AmbulanceLevel
from app.models.route import WaypointKind, WaypointSuggestionStatus


class EtaRange(BaseModel):
    min_minutes: int
    max_minutes: int


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    route_id: str
    case_id: str
    hospital_id: str
    route_polyline: str
    route_source: str
    route_note: str | None
    route_path: list[list[float]] | None = None
    eta_minutes: int
    eta_min_minutes: int
    eta_max_minutes: int
    distance_km: float | None
    created_at: datetime

    @property
    def eta_range(self) -> EtaRange:  # convenience; also exposed explicitly below
        return EtaRange(min_minutes=self.eta_min_minutes, max_minutes=self.eta_max_minutes)


class TrafficAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    traffic_alert_id: str
    case_id: str
    hospital_id: str
    eta_minutes: int
    eta_min_minutes: int
    eta_max_minutes: int
    traffic_alert_recipients: list[str]
    traffic_alert_sent_at: datetime


class WaypointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    waypoint_id: str
    name: str
    kind: WaypointKind
    latitude: float
    longitude: float
    has_oxygen: bool
    has_doctor: bool


class WaypointSuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    waypoint_suggestion_id: str
    case_id: str
    waypoint_id: str
    reason: str
    status: WaypointSuggestionStatus
    suggested_at: datetime
    decided_at: datetime | None
    decided_by: str | None


class WaypointDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    helper_id: str = Field(min_length=1)


class AmbulanceLevelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ambulance_level: AmbulanceLevel
