"""FR-4 orchestration: route + ETA, automatic traffic alert, waypoint suggestion."""
import math
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import TRAFFIC_ALERT_RECIPIENTS
from app.models.assessment import Assessment
from app.models.case import AmbulanceLevel, Case
from app.models.hospital import Hospital
from app.models.route import (
    CaseRoute,
    TrafficAlert,
    Waypoint,
    WaypointSuggestion,
    WaypointSuggestionStatus,
)
from app.services import maps

# --- FR-4 item 4: fixed keyword rule for "symptoms suggest ALS-level risk" -----
# Any one of these conditions flags the case as ALS-risk.
_ALS_RISK_SYMPTOM_COMBOS: list[set[str]] = [
    {"chest_pain", "breathing_difficulty"},
    {"unconsciousness"},
    {"seizure"},
    {"visible_bleeding", "trauma"},
]


class WaypointDecisionError(Exception):
    pass


def symptoms_indicate_als_risk(symptom_checklist: list[str]) -> bool:
    s = set(symptom_checklist)
    return any(combo.issubset(s) for combo in _ALS_RISK_SYMPTOM_COMBOS)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def get_route(db: Session, case_id: str) -> CaseRoute | None:
    return db.scalar(select(CaseRoute).where(CaseRoute.case_id == case_id))


def get_traffic_alert(db: Session, case_id: str) -> TrafficAlert | None:
    return db.scalar(select(TrafficAlert).where(TrafficAlert.case_id == case_id))


def get_waypoint_suggestion(db: Session, case_id: str) -> WaypointSuggestion | None:
    return db.scalar(select(WaypointSuggestion).where(WaypointSuggestion.case_id == case_id))


def _pick_waypoint(db: Session, origin, destination) -> Waypoint | None:
    """Nearest PHC/CHC with oxygen AND a doctor to the midpoint of the trip
    (a straight-line approximation of 'reasonably on the route')."""
    waypoints = list(db.scalars(select(Waypoint)))
    qualifying = [w for w in waypoints if w.has_oxygen and w.has_doctor]
    if not qualifying:
        qualifying = [w for w in waypoints if w.has_oxygen]
    if not qualifying or origin is None or destination is None:
        return qualifying[0] if qualifying else None
    mid_lat = (origin[0] + destination[0]) / 2
    mid_lon = (origin[1] + destination[1]) / 2
    return min(qualifying, key=lambda w: _haversine_km(mid_lat, mid_lon, w.latitude, w.longitude))


def run_for_case(db: Session, case: Case) -> CaseRoute:
    """Called right after a hospital is selected + bed-locked. Idempotent-ish:
    if a route already exists it is returned unchanged."""
    existing = get_route(db, case.case_id)
    if existing is not None:
        return existing

    hospital = db.get(Hospital, case.selected_hospital_id)
    assessment = db.scalar(select(Assessment).where(Assessment.case_id == case.case_id))
    symptoms = list(assessment.symptom_checklist) if assessment else []

    origin = (
        (case.gps_latitude, case.gps_longitude)
        if case.gps_latitude is not None and case.gps_longitude is not None
        else None
    )
    destination = (
        (hospital.latitude, hospital.longitude)
        if hospital and hospital.latitude is not None and hospital.longitude is not None
        else None
    )

    route_result = maps.get_route(
        origin, destination, fallback_eta_minutes=hospital.eta_minutes if hospital else 15
    )

    route = CaseRoute(
        case_id=case.case_id,
        hospital_id=case.selected_hospital_id,
        origin_latitude=origin[0] if origin else None,
        origin_longitude=origin[1] if origin else None,
        destination_latitude=destination[0] if destination else None,
        destination_longitude=destination[1] if destination else None,
        route_polyline=route_result.polyline,
        route_source=route_result.source,
        route_note=route_result.note,
        route_path=[list(p) for p in route_result.path],
        eta_minutes=route_result.eta_minutes,
        eta_min_minutes=route_result.eta_min_minutes,
        eta_max_minutes=route_result.eta_max_minutes,
        distance_km=route_result.distance_km,
    )
    db.add(route)

    # FR-4 item 3: a traffic alert for EVERY case, Path A and Path B alike.
    db.add(
        TrafficAlert(
            case_id=case.case_id,
            hospital_id=case.selected_hospital_id,
            route_polyline=route_result.polyline,
            eta_minutes=route_result.eta_minutes,
            eta_min_minutes=route_result.eta_min_minutes,
            eta_max_minutes=route_result.eta_max_minutes,
            traffic_alert_recipients=list(TRAFFIC_ALERT_RECIPIENTS),
            traffic_alert_sent_at=datetime.now(timezone.utc),
        )
    )

    # FR-4 item 4: ALS-risk symptoms + a BLS ambulance -> SUGGEST a waypoint.
    if (
        case.ambulance_level == AmbulanceLevel.BLS
        and symptoms_indicate_als_risk(symptoms)
    ):
        wp = _pick_waypoint(db, origin, destination)
        if wp is not None:
            db.add(
                WaypointSuggestion(
                    case_id=case.case_id,
                    waypoint_id=wp.waypoint_id,
                    reason=(
                        "Symptoms indicate ALS-level risk but a BLS ambulance is "
                        f"assigned; suggest stabilising at {wp.name} ({wp.kind.value})."
                    ),
                )
            )

    db.commit()
    db.refresh(route)
    return route


def decide_waypoint(db: Session, case_id: str, *, accept: bool, decided_by: str) -> WaypointSuggestion:
    suggestion = get_waypoint_suggestion(db, case_id)
    if suggestion is None:
        raise WaypointDecisionError(f"case '{case_id}' has no waypoint suggestion")
    if suggestion.status != WaypointSuggestionStatus.suggested:
        raise WaypointDecisionError(f"waypoint suggestion already {suggestion.status.value}")
    suggestion.status = (
        WaypointSuggestionStatus.accepted if accept else WaypointSuggestionStatus.declined
    )
    suggestion.decided_at = datetime.now(timezone.utc)
    suggestion.decided_by = decided_by
    db.commit()
    db.refresh(suggestion)
    return suggestion
