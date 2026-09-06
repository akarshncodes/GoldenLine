"""FR-9 tracking-link logic: token creation, closure expiry, scoped read-only view.

The read view exposes ONLY the whitelist in FRP FR-9 line 110/121:
hospital (name + why chosen: distance, rating, cost tier), live ETA range,
bed-lock status, prep status, QR-handoff status. Nothing else. No case_id,
no patient data, no other endpoints.
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import (
    TRACKING_LINK_BASE,
    TRACKING_TOKEN_EXPIRY_HOURS_AFTER_CLOSE,
    TRACKING_TOKEN_PLACEHOLDER_DAYS,
)
from app.models.bed_lock import BedLock, LockStatus
from app.models.case import Case, CaseStatus, CreationPath
from app.models.hospital import Hospital
from app.models.prep import PrepAction, PrepActionStatus
from app.models.route import CaseRoute
from app.models.sms import SmsCategory
from app.models.tracking import CaseTrackingToken
from app.services.sms import send_sms


class TokenExpired(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_token_row(db: Session, case_id: str) -> CaseTrackingToken | None:
    return db.scalar(select(CaseTrackingToken).where(CaseTrackingToken.case_id == case_id))


def create_for_path_b_case(db: Session, case: Case) -> CaseTrackingToken | None:
    """FR-9: the instant a Path B case is created, mint a token + 'send' the SMS.

    Path A cases never get one.
    """
    if case.creation_path != CreationPath.B:
        return None
    if get_token_row(db, case.case_id) is not None:
        return get_token_row(db, case.case_id)

    now = _utcnow()
    row = CaseTrackingToken(
        case_id=case.case_id,
        token=secrets.token_urlsafe(32),
        token_created_at=now,
        token_expires_at=now + timedelta(days=TRACKING_TOKEN_PLACEHOLDER_DAYS),
    )
    db.add(row)
    db.flush()

    link = f"{TRACKING_LINK_BASE}/{row.token}"
    send_sms(
        db,
        case.next_of_kin_phone_number,
        f"Track the ambulance and hospital status for your family member: {link} "
        "(no login needed).",
        category=SmsCategory.tracking_link,
        case_id=case.case_id,
    )
    db.commit()
    db.refresh(row)
    return row


def on_case_closed(db: Session, case: Case) -> CaseTrackingToken | None:
    """FR-9 step 2: recompute expiry to (closure + 24-48h) once the case closes."""
    row = get_token_row(db, case.case_id)
    if row is None:
        return None
    closed_at = case.discharged_at or _utcnow()
    if closed_at.tzinfo is not None:
        closed_at = closed_at.astimezone(timezone.utc).replace(tzinfo=None)
    row.token_expires_at = closed_at + timedelta(hours=TRACKING_TOKEN_EXPIRY_HOURS_AFTER_CLOSE)
    db.commit()
    db.refresh(row)
    return row


def _hospital_block(db: Session, case: Case) -> dict | None:
    if case.selected_hospital_id is None:
        return None
    h = db.get(Hospital, case.selected_hospital_id)
    if h is None:
        return None
    return {
        "name": h.name,
        "distance_km": h.distance_km,
        "rating": h.rating,
        "cost_tier": h.cost_tier,
        "why_chosen": (
            f"Closest capable hospital in the {h.cost_tier} tier "
            f"(~{h.distance_km} km away, rated {h.rating})."
        ),
    }


def _eta_block(db: Session, case: Case) -> dict | None:
    route = db.scalar(select(CaseRoute).where(CaseRoute.case_id == case.case_id))
    if route is None:
        return None
    return {"min_minutes": route.eta_min_minutes, "max_minutes": route.eta_max_minutes}


def _bed_lock_status(db: Session, case: Case) -> str:
    lock = db.scalar(
        select(BedLock).where(
            BedLock.case_id == case.case_id, BedLock.lock_status == LockStatus.active
        )
    )
    return "confirmed" if lock is not None else "not_yet"


def _prep_status(db: Session, case: Case) -> dict:
    actions = list(db.scalars(select(PrepAction).where(PrepAction.case_id == case.case_id)))
    return {
        "total": len(actions),
        "confirmed": sum(1 for a in actions if a.status == PrepActionStatus.confirmed),
        "updates": [
            {"item": a.label, "status": a.status.value}
            for a in sorted(actions, key=lambda a: (a.action_type.value, a.action_key))
        ],
    }


def _stage(case: Case) -> str:
    if case.status == CaseStatus.DISCHARGED:
        return "discharged"
    if case.status == CaseStatus.ADMITTED:
        return "arrived"
    return "en_route"


def get_tracking_view(db: Session, token: str) -> dict | None:
    """Look up by TOKEN only. None -> unknown token. Raises TokenExpired if past expiry."""
    row = db.scalar(select(CaseTrackingToken).where(CaseTrackingToken.token == token))
    if row is None:
        return None

    expires_at = row.token_expires_at
    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    if _utcnow() >= expires_at:
        raise TokenExpired()

    case = db.get(Case, row.case_id)
    if case is None:  # pragma: no cover - FK makes this impossible
        return None

    return {
        "status": "active",
        "stage": _stage(case),
        "hospital": _hospital_block(db, case),
        "eta": _eta_block(db, case),
        "bed_lock_status": _bed_lock_status(db, case),
        "prep_status": _prep_status(db, case),
        "qr_handoff_status": "confirmed" if case.admitted_at is not None else "not_yet",
    }
