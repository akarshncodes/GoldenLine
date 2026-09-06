"""FR-4 endpoints: route, traffic alert, waypoint suggestion, ambulance level."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.schemas.route import (
    AmbulanceLevelUpdate,
    RouteOut,
    TrafficAlertOut,
    WaypointDecisionRequest,
    WaypointSuggestionOut,
)
from app.services import route as svc

router = APIRouter(tags=["route"])


def _require_case(case_id: str, db: Session) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    return case


@router.put("/cases/{case_id}/ambulance-level", response_model=dict)
def set_ambulance_level(
    case_id: str, payload: AmbulanceLevelUpdate, db: Session = Depends(get_db)
) -> dict:
    """Set the assigned ambulance's capability level (default is BLS)."""
    case = _require_case(case_id, db)
    case.ambulance_level = payload.ambulance_level
    db.commit()
    return {"case_id": case_id, "ambulance_level": payload.ambulance_level.value}


@router.get("/cases/{case_id}/route", response_model=RouteOut)
def get_route(case_id: str, db: Session = Depends(get_db)) -> RouteOut:
    _require_case(case_id, db)
    route = svc.get_route(db, case_id)
    if route is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "no route yet — select and bed-lock a hospital first (FR-2/FR-3)",
        )
    return route


@router.get("/cases/{case_id}/traffic-alert", response_model=TrafficAlertOut)
def get_traffic_alert(case_id: str, db: Session = Depends(get_db)) -> TrafficAlertOut:
    _require_case(case_id, db)
    alert = svc.get_traffic_alert(db, case_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no traffic alert for this case yet")
    return alert


@router.get("/cases/{case_id}/waypoint-suggestion", response_model=WaypointSuggestionOut)
def get_waypoint_suggestion(case_id: str, db: Session = Depends(get_db)) -> WaypointSuggestionOut:
    _require_case(case_id, db)
    suggestion = svc.get_waypoint_suggestion(db, case_id)
    if suggestion is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "no waypoint suggested for this case (not an ALS-risk-on-BLS situation)",
        )
    return suggestion


@router.post("/cases/{case_id}/waypoint-suggestion/accept", response_model=WaypointSuggestionOut)
def accept_waypoint(
    case_id: str, payload: WaypointDecisionRequest, db: Session = Depends(get_db)
) -> WaypointSuggestionOut:
    """The helper explicitly accepts the suggested stop (never auto-applied)."""
    _require_case(case_id, db)
    try:
        return svc.decide_waypoint(db, case_id, accept=True, decided_by=payload.helper_id)
    except svc.WaypointDecisionError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.post("/cases/{case_id}/waypoint-suggestion/decline", response_model=WaypointSuggestionOut)
def decline_waypoint(
    case_id: str, payload: WaypointDecisionRequest, db: Session = Depends(get_db)
) -> WaypointSuggestionOut:
    _require_case(case_id, db)
    try:
        return svc.decide_waypoint(db, case_id, accept=False, decided_by=payload.helper_id)
    except svc.WaypointDecisionError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
