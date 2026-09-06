"""Map view: admin/control-room overview of the ambulance fleet.

Hospitals already have their own `GET /hospitals` (with lat/lng) and blood banks
their own `GET /blood-banks` — this is the missing third pin type. No new
tracking mechanism: an ambulance's "current" position is just its assigned
case's live gps fields, the same live location FR-2 ranking already reads.

Status is a 3-way read of existing case data, not a stored field: no active
case = idle; active case with no hospital chosen yet = still en route to pick
up the patient; hospital selected/bed locked = en route to hospital. This
mirrors exactly what a helper's own case-detail screen already shows —
there is deliberately no separate "ambulance status" concept to keep in sync.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.case import Case, CaseStatus
from app.models.control_room import Flag, FlagStatus, FlagType
from app.schemas.mapview import AmbulanceOut
from app.services.ambulance import FAKE_AMBULANCES
from app.services.auth_deps import require_role

router = APIRouter(tags=["map"])

_ACTIVE_STATUSES = (CaseStatus.SOS_TRIGGERED, CaseStatus.AMBULANCE_DISPATCHED, CaseStatus.OPEN)


def _stale_gps_flagged_case_ids(db: Session) -> set[str]:
    """Case ids named by a still-open (escalated, not yet human-resolved)
    FR-10 anomaly flag — reuses Control Room's existing detection, doesn't
    duplicate it. `Flag.related_case_ids` is a JSON list, so this is a
    Python-side filter rather than a JSON-containment query (small table,
    admin/control_room-only endpoint — not worth a JSON1 dependency)."""
    escalated = db.scalars(
        select(Flag).where(Flag.flag_type == FlagType.anomaly, Flag.status == FlagStatus.escalated)
    ).all()
    ids: set[str] = set()
    for flag in escalated:
        ids.update(flag.related_case_ids or [])
    return ids


@router.get(
    "/ambulances",
    response_model=list[AmbulanceOut],
    dependencies=[Depends(require_role(Role.admin, Role.control_room))],
)
def list_ambulances(db: Session = Depends(get_db)) -> list[AmbulanceOut]:
    active_cases = db.scalars(
        select(Case).where(Case.status.in_(_ACTIVE_STATUSES), Case.helper_id.is_not(None))
    ).all()
    by_helper: dict[str, Case] = {c.helper_id: c for c in active_cases}
    flagged_case_ids = _stale_gps_flagged_case_ids(db)

    out: list[AmbulanceOut] = []
    for amb in FAKE_AMBULANCES:
        case = by_helper.get(amb.helper_user_id)
        if case is not None:
            status_ = "en_route_to_hospital" if case.selected_hospital_id else "en_route_to_pickup"
            out.append(
                AmbulanceOut(
                    ambulance_id=amb.id,
                    vehicle_number=amb.vehicle_number,
                    helper_user_id=amb.helper_user_id,
                    base_latitude=amb.base_latitude,
                    base_longitude=amb.base_longitude,
                    status=status_,
                    case_id=case.case_id,
                    current_latitude=case.gps_latitude,
                    current_longitude=case.gps_longitude,
                    has_stale_gps_flag=case.case_id in flagged_case_ids,
                )
            )
        else:
            out.append(
                AmbulanceOut(
                    ambulance_id=amb.id,
                    vehicle_number=amb.vehicle_number,
                    helper_user_id=amb.helper_user_id,
                    base_latitude=amb.base_latitude,
                    base_longitude=amb.base_longitude,
                    status="idle",
                )
            )
    return out
