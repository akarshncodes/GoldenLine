"""FR-8 Discharge Feedback: trigger discharge (mock SMS), submit structured tags once."""
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import FEEDBACK_LINK_BASE
from app.models.case import Case, CaseStatus
from app.models.feedback import CaseFeedback, FeedbackInvite, ReadyAsShownTag
from app.models.sms import SmsCategory
from app.services.sms import send_sms


class DischargeNotAllowed(Exception):
    pass


class FeedbackNotAllowed(Exception):
    pass


class FeedbackAlreadySubmitted(Exception):
    """Raised when the DB unique constraint on case_feedback.case_id rejects a
    second submission."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_invite(db: Session, case_id: str) -> FeedbackInvite | None:
    return db.scalar(select(FeedbackInvite).where(FeedbackInvite.case_id == case_id))


def get_feedback(db: Session, case_id: str) -> CaseFeedback | None:
    return db.scalar(select(CaseFeedback).where(CaseFeedback.case_id == case_id))


def trigger_discharge(db: Session, case: Case) -> FeedbackInvite:
    """Simulates the 'days later' job: mark discharged + send the feedback link."""
    if case.status == CaseStatus.DISCHARGED:
        raise DischargeNotAllowed("case is already discharged")
    if case.status != CaseStatus.ADMITTED:
        raise DischargeNotAllowed("case must be admitted (a valid QR handoff) before discharge")

    now = _utcnow()
    case.status = CaseStatus.DISCHARGED
    case.discharged_at = now

    # FR-16: give the admitted bed back — explicit, audited, tied to this discharge
    # (the counterpart to the QR-handoff admission decrement). Never breaks discharge.
    try:
        from app.services import hospital_sync

        hospital_sync.record_discharge_increment(db, case=case)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception(
            "FR-16 discharge bed re-increment failed for case %s", case.case_id
        )

    # FR-18: close out this case's census entry too (visibility-only — the bed
    # was already credited back above). Never breaks discharge.
    try:
        from app.services import patients as patients_svc

        patients_svc.discharge_census_entry_for_case(db, case=case)
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception(
            "FR-18 census discharge failed for case %s", case.case_id
        )

    token = secrets.token_urlsafe(24)
    link = f"{FEEDBACK_LINK_BASE}/{token}"
    invite = FeedbackInvite(
        case_id=case.case_id,
        token=token,
        link=link,
        recipient_phone=case.next_of_kin_phone_number or case.family_phone_number,
        sms_sent_at=now,
    )
    db.add(invite)

    # One messaging system (FRP FR-9 note): route this through the shared SMS seam.
    send_sms(
        db,
        invite.recipient_phone,
        f"How was your hospital experience? Share quick feedback: {link}",
        category=SmsCategory.discharge_feedback,
        case_id=case.case_id,
    )

    # FR-9 step 2: recompute the family tracking-link expiry now the case closed.
    try:
        from app.services import tracking as tracking_svc

        tracking_svc.on_case_closed(db, case)
    except Exception:  # noqa: BLE001
        pass

    db.commit()
    db.refresh(invite)
    return invite


def submit_feedback(
    db: Session,
    *,
    case_id: str,
    token: str,
    wait_time_tag: int,
    staff_behavior_tag: int,
    cleanliness_tag: int,
    billing_tag: int,
    ready_as_shown_tag: ReadyAsShownTag,
) -> CaseFeedback:
    case = db.get(Case, case_id)
    if case is None:
        raise FeedbackNotAllowed("case not found")
    if case.status != CaseStatus.DISCHARGED:
        raise FeedbackNotAllowed("feedback opens only after the case is discharged")

    invite = get_invite(db, case_id)
    if invite is None or invite.token != token:
        raise FeedbackNotAllowed("invalid feedback link")

    feedback = CaseFeedback(
        case_id=case_id,
        hospital_id=case.selected_hospital_id,
        wait_time_tag=wait_time_tag,
        staff_behavior_tag=staff_behavior_tag,
        cleanliness_tag=cleanliness_tag,
        billing_tag=billing_tag,
        ready_as_shown_tag=ready_as_shown_tag,
    )
    db.add(feedback)
    try:
        db.commit()
    except IntegrityError:
        # The DB unique constraint on case_feedback.case_id rejected a duplicate.
        db.rollback()
        raise FeedbackAlreadySubmitted(case_id)
    db.refresh(feedback)
    return feedback
