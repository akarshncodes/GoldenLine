"""FR-0 Case Creation endpoints (Path A and Path B) + FR-11/FR-12 hardening."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.case import Case
from app.schemas.case import (
    AmbulanceOut,
    CaseResponse,
    CaseSummary,
    HelperLocationUpdate,
    PathASosRequest,
    PathBCreateRequest,
    SosResponse,
)
from app.schemas.ambulance import AmbulanceSummaryOut
from app.services import cases as cases_service
from app.services import dedup, ratelimit
from app.services import otp as otp_svc
from app.services.access import can_see_case, require_case_access
from app.services.ambulance import NoAmbulanceAvailable, get_ambulance_for_helper
from app.services.auth_deps import get_principal, require_role
from app.services.security import Principal

router = APIRouter(prefix="/cases", tags=["cases"])

_HELPER_LOCATION_NOTE = (
    "The dispatched ambulance's helper is already assigned to this case, but its "
    "location is not set yet. It must be reported from the helper's device via "
    "POST /cases/{case_id}/helper-location — never from the family's phone."
)


@router.post("/sos", response_model=SosResponse, status_code=status.HTTP_201_CREATED)
def create_case_path_a(payload: PathASosRequest, db: Session = Depends(get_db)) -> SosResponse:
    """Path A — family SOS. Requires a verified OTP (FR-12). Near-duplicate SOS
    requests auto-merge into one case. A request burst is flagged, never blocked."""
    # FR-12: rate-limit FLAG (never block).
    flag = ratelimit.record_and_maybe_flag(
        db, source=f"phone:{payload.family_phone_number}", source_type="phone"
    )
    if flag is not None:
        db.commit()

    # FR-12: the family's phone must have a verified, unused OTP for this request.
    try:
        otp_svc.consume_verified_otp(db, payload.otp_verification_id, payload.family_phone_number)
    except otp_svc.OtpError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"OTP verification failed: {exc}")

    # FR-12: duplicate auto-merge (same rough location + short time window).
    match = dedup.find_mergeable_path_a_case(
        db, latitude=payload.family_gps.latitude, longitude=payload.family_gps.longitude
    )
    if match is not None:
        existing, dist_m, secs = match
        log = dedup.log_merge(
            db,
            primary_case=existing,
            duplicate_source=f"phone:{payload.family_phone_number}",
            latitude=payload.family_gps.latitude,
            longitude=payload.family_gps.longitude,
            distance_m=dist_m,
            seconds_apart=secs,
        )
        db.commit()
        db.refresh(existing)
        return SosResponse(
            case=CaseResponse.model_validate(existing),
            dispatched_ambulance=None,
            note="Merged into an existing nearby SOS from the last few minutes.",
            merged_into_existing_case=True,
            merge_reason=log.reason,
            rate_limit_flagged=flag is not None,
        )

    family_user_id = f"family:{payload.family_phone_number}"
    try:
        case, ambulance, distance_km = cases_service.create_path_a_case(
            db, payload, family_user_id=family_user_id
        )
    except NoAmbulanceAvailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No registered ambulance available. Self-transport via the family's "
                "GPS is not supported (intentional limitation, FR-0 item 5)."
            ),
        )

    return SosResponse(
        case=CaseResponse.model_validate(case),
        dispatched_ambulance=AmbulanceOut(
            id=ambulance.id,
            vehicle_number=ambulance.vehicle_number,
            driver_name=ambulance.driver_name,
            driver_phone=ambulance.driver_phone,
            helper_user_id=ambulance.helper_user_id,
            base_latitude=ambulance.base_latitude,
            base_longitude=ambulance.base_longitude,
            distance_km=distance_km,
        ),
        note=_HELPER_LOCATION_NOTE,
        rate_limit_flagged=flag is not None,
    )


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case_path_b(
    payload: PathBCreateRequest,
    principal: Principal = Depends(require_role(Role.helper)),
    db: Session = Depends(get_db),
) -> Case:
    """Path B — the helper starts a case directly. Requires an authenticated
    helper account (FR-12): no per-case OTP, but not an anonymous request either."""
    ratelimit.record_and_maybe_flag(db, source=f"user:{principal.user_id}", source_type="user")
    return cases_service.create_path_b_case(db, payload)


@router.get("", response_model=list[CaseSummary])
def list_cases(
    request: Request,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
) -> list[Case]:
    """Cases visible to the caller (FR-11 scoping), newest first.

    admin / control_room → all; helper → their own; hospital_receptionist →
    cases routed to their hospital; family → their own; blood_bank_coordinator →
    cases with a hold at their bank. Optional `?status_filter=OPEN,ADMITTED`.
    """
    principal = get_principal(request)
    wanted = (
        {s.strip().upper() for s in status_filter.split(",") if s.strip()}
        if status_filter
        else None
    )
    rows = db.scalars(select(Case).order_by(Case.created_at.desc())).all()
    out = [
        c for c in rows
        if can_see_case(db, principal, c)
        and (wanted is None or c.status.value in wanted)
    ]
    return out


@router.post("/{case_id}/helper-location", response_model=CaseResponse)
def update_helper_location(
    case_id: str, payload: HelperLocationUpdate, request: Request, db: Session = Depends(get_db)
) -> Case:
    """Report the helper device location for a case (scoped to the case owner)."""
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    require_case_access(db, get_principal(request), case)
    return cases_service.set_helper_location(db, case, payload)


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: str, request: Request, db: Session = Depends(get_db)) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    return require_case_access(db, get_principal(request), case)


@router.get("/{case_id}/ambulance", response_model=AmbulanceSummaryOut)
def get_case_ambulance(case_id: str, request: Request, db: Session = Depends(get_db)) -> AmbulanceSummaryOut:
    """Which ambulance is assigned to this case, and its live position — the
    SAME case.gps_latitude/longitude the FR-2 ranking distance calc already
    reads, just resolved to a human-readable vehicle/driver identity. No
    driver phone number here on purpose (family-facing privacy decision)."""
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="case not found")
    require_case_access(db, get_principal(request), case)

    amb = get_ambulance_for_helper(case.helper_id) if case.helper_id else None
    if amb is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no ambulance assigned to this case yet")

    return AmbulanceSummaryOut(
        ambulance_id=amb.id,
        vehicle_number=amb.vehicle_number,
        driver_name=amb.driver_name,
        latitude=case.gps_latitude,
        longitude=case.gps_longitude,
        gps_timestamp=case.gps_timestamp,
    )
