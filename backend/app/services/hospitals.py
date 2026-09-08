"""FR-2 hospital selection (+ FR-3 auto bed lock, + FR-4/FR-5 post-selection steps)."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bed_lock import BedLock
from app.models.case import Case
from app.models.hospital import Hospital
from app.services import assessment as assessment_svc
from app.services import bed_lock as bed_lock_svc
from app.services import blood as blood_svc
from app.services import prep as prep_svc
from app.services import route as route_svc
from app.services.hospital_ranking import (
    RankingResult,
    best_in_class,
    rank_hospitals,
    required_specialties_for,
)

logger = logging.getLogger(__name__)


class SymptomsNotLogged(Exception):
    """FR-2 precondition (FRP line 153): FR-1 assessment must exist first."""


class HospitalAlreadySelected(Exception):
    pass


class HospitalNotInRankedList(Exception):
    pass


class NoRankedHospitals(Exception):
    pass


def list_hospitals(db: Session) -> list[Hospital]:
    return list(db.scalars(select(Hospital).order_by(Hospital.hospital_id)))


def get_hospital(db: Session, hospital_id: str) -> Hospital | None:
    return db.get(Hospital, hospital_id)


def rank_for_case(db: Session, case: Case) -> RankingResult:
    assessment = assessment_svc.get_assessment(db, case.case_id)
    if assessment is None:
        raise SymptomsNotLogged()

    required = required_specialties_for(list(assessment.symptom_checklist))
    bed_type = bed_lock_svc.bed_type_for_criticality(assessment.criticality_level)
    case_location = (
        (case.gps_latitude, case.gps_longitude)
        if case.gps_latitude is not None and case.gps_longitude is not None
        else None
    )
    return rank_hospitals(
        list_hospitals(db),
        required_specialties=required,
        case_scheme=case.government_scheme,
        availability=bed_lock_svc.availability_map(db),
        bed_type_needed=bed_type.value,
        case_location=case_location,
    )


def _apply_selection_fields(case: Case, hospital_id: str, by: str, via: str) -> None:
    case.selected_hospital_id = hospital_id
    case.selected_by = by
    case.selected_via = via
    case.selection_timestamp = datetime.now(timezone.utc)


def _select_and_lock(db: Session, case: Case, hospital_id: str, by: str, via: str) -> tuple[Case, BedLock]:
    """FR-3 item 1: the instant a hospital is chosen, hold one bed for the case.

    The bed lock is committed first (its own atomic transaction). Only if that
    succeeds do we record the selection on the case. A BedLockConflict propagates
    to the caller with nothing selected, so the family/helper can pick another.
    """
    bed_type = bed_lock_svc.bed_type_for_case(db, case)
    lock = bed_lock_svc.acquire_lock(db, hospital_id, case.case_id, bed_type)  # commits or raises
    _apply_selection_fields(case, hospital_id, by, via)
    db.commit()
    db.refresh(case)

    # FR-4 (route + traffic alert + maybe waypoint) and FR-5 (blood check, only
    # when bleeding/trauma). Downstream of the reservation — a failure here must
    # not undo the selection or the bed lock.
    try:
        route_svc.run_for_case(db, case)
    except Exception:  # noqa: BLE001
        logger.exception("FR-4 route step failed for case %s", case.case_id)
    try:
        blood_svc.run_for_case(db, case)
    except Exception:  # noqa: BLE001
        logger.exception("FR-5 blood step failed for case %s", case.case_id)
    try:
        prep_svc.generate_for_case(db, case)
    except Exception:  # noqa: BLE001
        logger.exception("FR-6 prep step failed for case %s", case.case_id)

    db.refresh(case)
    return case, lock


def select_hospital_by_helper(
    db: Session, case: Case, hospital_id: str, helper_id: str
) -> tuple[Case, BedLock]:
    """Both paths: the helper taps one of the 3 cost-class hospitals shown for
    this case, after asking the family which class they'd like — never the
    family directly, never auto-selected, and never any hospital outside those
    3 picks.
    """
    if case.selected_hospital_id is not None:
        raise HospitalAlreadySelected()
    result = rank_for_case(db, case)
    if not result.ranked:
        raise NoRankedHospitals()
    valid = {h.hospital_id for h in best_in_class(result.ranked).values() if h is not None}
    if hospital_id not in valid:
        raise HospitalNotInRankedList()
    return _select_and_lock(db, case, hospital_id, by=helper_id, via="helper_confirm")


def clear_selection(db: Session, case: Case) -> None:
    """Used when a case is reassigned after its bed lock is released."""
    case.selected_hospital_id = None
    case.selected_by = None
    case.selected_via = None
    case.selection_timestamp = None
    db.commit()
