"""FR-3 Bed Lock endpoints: view a case's lock, release it, dashboard, conflicts."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.case import Case
from app.schemas.bed_lock import (
    ActiveLockOut,
    BedLockOut,
    ConflictLogOut,
    HospitalDashboardRow,
    ReleaseResponse,
)
from app.services import bed_lock as svc
from app.services import hospitals as hospitals_svc
from app.services.auth_deps import get_principal, require_role
from app.services.security import Principal

router = APIRouter(tags=["bed-locks"])


@router.get("/hospitals/dashboard", response_model=list[HospitalDashboardRow])
def hospital_dashboard(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[HospitalDashboardRow]:
    """Live available beds per hospital, accounting for active locks (FR-3 item 6).

    A hospital receptionist sees only their own hospital's row (FR-11).
    """
    rows: list[HospitalDashboardRow] = []
    for a in svc.availability_for_all(db):
        if (
            principal.role == Role.hospital_receptionist
            and not principal.is_privileged
            and a.hospital_id != principal.hospital_id
        ):
            continue
        locks = svc.active_locks_for_hospital(db, a.hospital_id)
        rows.append(
            HospitalDashboardRow(
                hospital_id=a.hospital_id,
                name=a.name,
                total_general_beds=a.total_general_beds,
                active_general_locks=a.active_general_locks,
                reserved_general_beds=a.reserved_general_beds,
                available_general_beds=a.available_general_beds,
                total_icu_beds=a.total_icu_beds,
                active_icu_locks=a.active_icu_locks,
                reserved_icu_beds=a.reserved_icu_beds,
                available_icu_beds=a.available_icu_beds,
                locked_for_cases=[ActiveLockOut.model_validate(lock) for lock in locks],
            )
        )
    return rows


@router.get("/bed-locks/conflicts", response_model=list[ConflictLogOut])
def list_conflicts(
    principal: Principal = Depends(require_role(Role.control_room, Role.admin)),
    db: Session = Depends(get_db),
) -> list[ConflictLogOut]:
    """Every recorded bed-lock collision (FR-3 item 5). Control Room / admin only."""
    return svc.list_conflicts(db)


@router.get("/cases/{case_id}/bed-lock", response_model=BedLockOut)
def get_case_bed_lock(case_id: str, db: Session = Depends(get_db)) -> BedLockOut:
    lock = svc.get_active_lock(db, case_id)
    if lock is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' has no active bed lock")
    return lock


@router.post("/cases/{case_id}/bed-lock/release", response_model=ReleaseResponse)
def release_case_bed_lock(case_id: str, db: Session = Depends(get_db)) -> ReleaseResponse:
    """Release the case's bed (cancelled / reassigned). The bed frees up immediately,
    and the case's hospital selection is cleared so it can be re-selected (FR-3 item 4)."""
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    try:
        released = svc.release_lock(db, case_id)
    except svc.NoActiveLock:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' has no active bed lock")

    hospitals_svc.clear_selection(db, case)

    avail = {a.hospital_id: a for a in svc.availability_for_all(db)}[released.hospital_id]
    return ReleaseResponse(
        released_lock=BedLockOut.model_validate(released),
        hospital_id=released.hospital_id,
        bed_type=released.bed_type,
        available_general_beds=avail.available_general_beds,
        available_icu_beds=avail.available_icu_beds,
        case_selection_cleared=True,
    )
