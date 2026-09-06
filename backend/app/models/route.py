"""FR-4 Route, Traffic Coordination and Waypoint Check."""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WaypointKind(str, enum.Enum):
    PHC = "PHC"  # Primary Health Centre
    CHC = "CHC"  # Community Health Centre


class WaypointSuggestionStatus(str, enum.Enum):
    suggested = "suggested"
    accepted = "accepted"
    declined = "declined"


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaseRoute(Base):
    """The live route + ETA for a case, from the Maps API (or a clearly-marked stub)."""
    __tablename__ = "case_routes"

    route_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), unique=True, nullable=False)
    hospital_id: Mapped[str] = mapped_column(String(32), nullable=False)

    origin_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    origin_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    route_polyline: Mapped[str] = mapped_column(Text, nullable=False)
    route_source: Mapped[str] = mapped_column(String(20), nullable=False)  # 'google_maps' | 'osrm' | 'stub'
    route_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Drawable [[lat, lon], ...] points for the map view, regardless of route_source.
    route_path: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # ETA is always a RANGE (FR-4 / FR-14 safe-driving). eta_minutes is the point estimate.
    eta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_min_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_max_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class TrafficAlert(Base):
    """Auto-created for EVERY case (Path A and Path B) once a route exists."""
    __tablename__ = "traffic_alerts"

    traffic_alert_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), unique=True, nullable=False)
    hospital_id: Mapped[str] = mapped_column(String(32), nullable=False)

    route_polyline: Mapped[str] = mapped_column(Text, nullable=False)
    eta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_min_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    eta_max_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    traffic_alert_recipients: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    traffic_alert_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class Waypoint(Base):
    """Seeded PHC/CHC stabilization points."""
    __tablename__ = "waypoints"

    waypoint_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[WaypointKind] = mapped_column(SAEnum(WaypointKind, native_enum=False, length=3), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    has_oxygen: Mapped[bool] = mapped_column(Boolean, nullable=False)
    has_doctor: Mapped[bool] = mapped_column(Boolean, nullable=False)


class WaypointSuggestion(Base):
    """A SUGGESTED stabilization stop — never applied without the helper's tap."""
    __tablename__ = "waypoint_suggestions"

    waypoint_suggestion_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), unique=True, nullable=False)
    waypoint_id: Mapped[str] = mapped_column(String(32), ForeignKey("waypoints.waypoint_id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[WaypointSuggestionStatus] = mapped_column(
        SAEnum(WaypointSuggestionStatus, native_enum=False, length=12),
        nullable=False,
        default=WaypointSuggestionStatus.suggested,
    )
    suggested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
