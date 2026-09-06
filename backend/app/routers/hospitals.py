"""FR-2 endpoints: hospital list, per-case ranking, scheme flag, final selection.

FR-3 hook: a successful selection/confirmation also places an atomic bed lock.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.schemas.bed_lock import BedLockOut
from app.schemas.hospital import (
    HospitalOut,
    HospitalSelectionRequest,
    RankedHospitalOut,
    RankingResponse,
    SchemeUpdate,
    SelectionResponse,
)
from app.models.auth import Role
from app.services import bed_lock as bed_lock_svc
from app.services import hospitals as svc
from app.services.access import require_case_access
from app.services.auth_deps import get_principal, require_role
from app.services.hospital_ranking import best_in_class
from app.services.security import Principal

router = APIRouter(tags=["hospitals"])


def _require_case(case_id: str, db: Session) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    return case


def _selection_response(case: Case, lock) -> SelectionResponse:
    return SelectionResponse(
        case_id=case.case_id,
        creation_path=case.creation_path.value,
        selected_hospital_id=case.selected_hospital_id,
        selected_by=case.selected_by,
        selected_via=case.selected_via,
        selection_timestamp=case.selection_timestamp,
        bed_lock=BedLockOut.model_validate(lock) if lock is not None else None,
    )


def _bed_lock_conflict(exc: bed_lock_svc.BedLockConflict) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={
            "error": "bed_lock_conflict",
            "message": str(exc),
            "hospital_id": exc.hospital_id,
            "bed_type": exc.bed_type.value,
            "held_by_case_id": exc.holder_case_id,
            "note": "no hospital was selected — pick a different hospital; a conflict_log row was recorded",
        },
    )


@router.get("/hospitals", response_model=list[HospitalOut])
def list_hospitals(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[HospitalOut]:
    """The mock hospital dataset. A hospital receptionist sees only their own hospital (FR-11)."""
    rows = svc.list_hospitals(db)
    if principal.role == Role.hospital_receptionist and not principal.is_privileged:
        rows = [h for h in rows if h.hospital_id == principal.hospital_id]
    return rows


@router.put("/cases/{case_id}/scheme", response_model=SelectionResponse)
def set_case_scheme(case_id: str, payload: SchemeUpdate, db: Session = Depends(get_db)) -> SelectionResponse:
    """Record (or clear) the government scheme the family/helper indicated."""
    case = _require_case(case_id, db)
    case.government_scheme = payload.government_scheme
    db.commit()
    db.refresh(case)
    return _selection_response(case, bed_lock_svc.get_active_lock(db, case.case_id))


@router.get("/cases/{case_id}/hospital-ranking", response_model=RankingResponse)
def get_hospital_ranking(case_id: str, db: Session = Depends(get_db)) -> RankingResponse:
    """The ranked list for this case, plus the helper's actual choice screen
    (`classes`: one best hospital per cost class). Read-only — never selects.

    Hospitals with no free bed of the type this case needs (net of active locks)
    are excluded (FR-3 item 2).
    """
    case = _require_case(case_id, db)
    try:
        result = svc.rank_for_case(db, case)
    except svc.SymptomsNotLogged:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "log symptoms first (FR-1) — ranking needs the case's symptom_checklist",
        )
    return RankingResponse(
        case_id=case.case_id,
        creation_path=case.creation_path.value,
        case_scheme=result.case_scheme,
        required_specialties=result.required_specialties,
        bed_type_needed=result.bed_type_needed,
        excluded_hospital_ids=result.excluded_hospital_ids,
        excluded_no_capacity_ids=result.excluded_no_capacity_ids,
        explanation=result.explanation,
        ranked=[RankedHospitalOut.model_validate(h) for h in result.ranked],
        distance_source=result.distance_source,
        classes={
            cls: (RankedHospitalOut.model_validate(h) if h is not None else None)
            for cls, h in best_in_class(result.ranked).items()
        },
    )


@router.post(
    "/cases/{case_id}/select-hospital",
    response_model=SelectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def select_hospital_path_a(
    case_id: str,
    payload: HospitalSelectionRequest,
    principal: Principal = Depends(require_role(Role.helper)),
    db: Session = Depends(get_db),
) -> SelectionResponse:
    """Path A final selection — the helper's explicit tap on one of the 3
    cost-class hospitals, made after asking the family which class they want."""
    case = _require_case(case_id, db)
    if case.creation_path.value != "A":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "this is a Path B case — use POST /cases/{case_id}/confirm-hospital",
        )
    require_case_access(db, principal, case)
    return _select(db, case, payload)


@router.post(
    "/cases/{case_id}/confirm-hospital",
    response_model=SelectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def confirm_hospital_path_b(
    case_id: str,
    payload: HospitalSelectionRequest,
    principal: Principal = Depends(require_role(Role.helper)),
    db: Session = Depends(get_db),
) -> SelectionResponse:
    """Path B final selection — the helper's explicit tap on one of the 3
    cost-class hospitals, made after asking the family which class they want."""
    case = _require_case(case_id, db)
    if case.creation_path.value != "B":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "this is a Path A case — use POST /cases/{case_id}/select-hospital",
        )
    require_case_access(db, principal, case)
    return _select(db, case, payload)


def _select(db: Session, case: Case, payload: HospitalSelectionRequest) -> SelectionResponse:
    try:
        case, lock = svc.select_hospital_by_helper(db, case, payload.hospital_id, payload.helper_id)
        return _selection_response(case, lock)
    except svc.HospitalAlreadySelected:
        raise HTTPException(status.HTTP_409_CONFLICT, "a hospital is already selected for this case")
    except svc.SymptomsNotLogged:
        raise HTTPException(status.HTTP_409_CONFLICT, "log symptoms first (FR-1)")
    except svc.NoRankedHospitals:
        raise HTTPException(status.HTTP_409_CONFLICT, "no hospital can handle this case's symptoms")
    except svc.HospitalNotInRankedList:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"hospital '{payload.hospital_id}' is not one of this case's 3 cost-class picks",
        )
    except bed_lock_svc.BedLockConflict as exc:
        raise _bed_lock_conflict(exc)
