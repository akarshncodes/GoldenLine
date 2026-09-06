"""Case-creation business logic for FR-0 (both paths)."""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.case import Case, CaseStatus, CreationPath
from app.schemas.case import HelperLocationUpdate, PathASosRequest, PathBCreateRequest
from app.services.ambulance import FakeAmbulance, find_nearest_ambulance

logger = logging.getLogger(__name__)


def create_path_a_case(
    db: Session, payload: PathASosRequest, *, family_user_id: str | None = None
) -> tuple[Case, FakeAmbulance, float]:
    """Path A: create a case from a family SOS and mock-dispatch the nearest ambulance.

    Real 108-style dispatch sends the driver AND a helper together — so the
    case's helper is the dispatched ambulance's fixed helper, known immediately
    (see FakeAmbulance.helper_user_id), no separate "claim this case" step.
    The family's phone GPS is used ONLY to pick the ambulance. It is NOT written
    to the case location — that must come from the helper's device once they
    arrive on scene.
    """
    ambulance, distance_km = find_nearest_ambulance(
        payload.family_gps.latitude, payload.family_gps.longitude
    )

    case = Case(
        creation_path=CreationPath.A,
        family_phone_number=payload.family_phone_number,
        family_user_id=family_user_id,
        helper_id=ambulance.helper_user_id,
        dispatched_ambulance_id=ambulance.id,
        status=CaseStatus.AMBULANCE_DISPATCHED,
        # audit-only: what the family's phone reported at SOS time (used to pick
        # the ambulance). NOT the authoritative case location — see model notes.
        sos_trigger_latitude=payload.family_gps.latitude,
        sos_trigger_longitude=payload.family_gps.longitude,
        sos_trigger_timestamp=payload.family_gps.timestamp or datetime.now(timezone.utc),
    )
    if payload.patient is not None:
        case.patient_name = payload.patient.name
        case.patient_approx_age = payload.patient.approx_age
        case.patient_gender = payload.patient.gender

    db.add(case)
    db.commit()
    db.refresh(case)
    return case, ambulance, distance_km


def create_path_b_case(db: Session, payload: PathBCreateRequest) -> Case:
    """Path B: the helper starts the case directly; case location = helper device GPS."""
    case = Case(
        creation_path=CreationPath.B,
        patient_name=payload.patient.name,
        patient_approx_age=payload.patient.approx_age,
        patient_gender=payload.patient.gender,
        next_of_kin_phone_number=payload.next_of_kin_phone_number,
        helper_id=payload.helper_id,
        gps_latitude=payload.helper_gps.latitude,
        gps_longitude=payload.helper_gps.longitude,
        gps_timestamp=payload.helper_gps.timestamp or datetime.now(timezone.utc),
        gps_source="helper_device",
        status=CaseStatus.OPEN,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    # FR-9: the instant a Path B case exists, mint the family tracking token +
    # "send" the SMS. A failure here must not fail case creation.
    try:
        from app.services import tracking as tracking_svc

        tracking_svc.create_for_path_b_case(db, case)
    except Exception:  # noqa: BLE001
        logger.exception("FR-9 tracking-token step failed for case %s", case.case_id)

    db.refresh(case)
    return case


def set_helper_location(
    db: Session, case: Case, payload: HelperLocationUpdate
) -> Case:
    """Set/refresh the case location from the helper's device (both paths)."""
    case.helper_id = payload.helper_id
    case.gps_latitude = payload.gps.latitude
    case.gps_longitude = payload.gps.longitude
    case.gps_timestamp = payload.gps.timestamp or datetime.now(timezone.utc)
    case.gps_source = "helper_device"
    db.commit()
    db.refresh(case)
    return case
