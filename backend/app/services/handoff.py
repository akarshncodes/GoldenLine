"""FR-7 QR Handoff: generate a short-lived token, scan it, return admission data."""
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import HANDOFF_CODE_ALPHABET, HANDOFF_CODE_LENGTH, QR_TOKEN_TTL_MINUTES
from app.models.assessment import Assessment
from app.models.case import Case, CaseStatus
from app.models.handoff import QrHandoffToken
from app.services.timeline import build_transit_timeline


class HandoffNotReady(Exception):
    """The case has not reached the point where a handoff QR makes sense."""


class InvalidHandoffToken(Exception):
    """Token missing / wrong case / expired / already used. Deliberately vague —
    the caller must not leak which, and must return no case data."""


def _utcnow() -> datetime:
    # Naive UTC — matches how SQLAlchemy's SQLite DateTime stores/returns values,
    # so token-expiry comparisons work both in Python and in SQL.
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class QrPayload:
    case_id: str
    token: str
    expires_at: datetime


def _new_handoff_code(db: Session) -> str:
    """Short human-readable code, not a scannable QR — read aloud or typed in
    by hand at the hospital desk. Retries on the rare collision."""
    for _ in range(10):
        code = "".join(secrets.choice(HANDOFF_CODE_ALPHABET) for _ in range(HANDOFF_CODE_LENGTH))
        if db.scalar(select(QrHandoffToken).where(QrHandoffToken.token == code)) is None:
            return code
    raise RuntimeError("could not generate a unique handoff code")


def generate_token(db: Session, case: Case) -> QrPayload:
    if case.selected_hospital_id is None:
        raise HandoffNotReady("select and bed-lock a hospital before generating a handoff QR")

    # Invalidate any earlier unused token for this case — only the QR now on
    # screen should be scannable.
    now = _utcnow()
    for old in db.scalars(
        select(QrHandoffToken).where(
            QrHandoffToken.case_id == case.case_id,
            QrHandoffToken.used_at.is_(None),
            QrHandoffToken.expires_at > now,
        )
    ):
        old.expires_at = now

    token = QrHandoffToken(
        case_id=case.case_id,
        token=_new_handoff_code(db),
        expires_at=now + timedelta(minutes=QR_TOKEN_TTL_MINUTES),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return QrPayload(case_id=case.case_id, token=token.token, expires_at=token.expires_at)


def _admission_bundle(db: Session, case: Case) -> dict:
    assessment = db.scalar(select(Assessment).where(Assessment.case_id == case.case_id))
    next_of_kin = case.next_of_kin_phone_number or case.family_phone_number

    return {
        "case_id": case.case_id,
        "creation_path": case.creation_path.value,
        "status": case.status.value,
        "transit_timeline": [
            {"event": e.event, "at": e.at.isoformat(), "detail": e.detail}
            for e in build_transit_timeline(db, case)
        ],
        "logged_symptoms": (
            {
                "criticality_level": assessment.criticality_level.value,
                "symptom_checklist": list(assessment.symptom_checklist),
                "input_method": assessment.input_method.value,
            }
            if assessment
            else None
        ),
        "admission_ready_data": {
            "patient_identity": {
                "name": case.patient_name,
                "approx_age": case.patient_approx_age,
                "gender": case.patient_gender.value if case.patient_gender else None,
            },
            "known_allergies": case.known_allergies,
            "current_medications": case.current_medications,
            "blood_group": case.blood_group,
            "next_of_kin": next_of_kin,
            "scheme_status": case.government_scheme or "not_indicated",
        },
    }


def scan(db: Session, *, case_id: str, token_value: str, scanned_by: str) -> dict:
    now = _utcnow()
    token = db.scalar(select(QrHandoffToken).where(QrHandoffToken.token == token_value))

    if (
        token is None
        or token.case_id != case_id
        or token.used_at is not None
        or token.expires_at <= now
    ):
        raise InvalidHandoffToken()

    case = db.get(Case, case_id)
    if case is None:
        raise InvalidHandoffToken()

    # consume the token and confirm admission
    token.used_at = now
    token.used_by = scanned_by
    if case.status != CaseStatus.ADMITTED:
        case.status = CaseStatus.ADMITTED
        case.admitted_at = now
        case.admitted_by = scanned_by
        # FR-16 item 3: auto-decrement the admitting hospital's live bed count,
        # tied to THIS exact handoff event (never inferred elsewhere, never silent).
        from app.services import hospital_sync

        hospital_sync.record_admission_decrement(
            db, case=case, handoff_token=token, admitted_by=scanned_by
        )
        # FR-18: give this case its own visibility-only entry in the hospital-wide
        # census — the bed count was already decremented above, this does not
        # decrement again.
        from app.services import patients as patients_svc

        patients_svc.create_census_entry_for_case_admission(db, case=case, handoff_token=token)
    db.commit()
    db.refresh(case)

    return _admission_bundle(db, case)
