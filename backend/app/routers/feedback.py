"""FR-8 Discharge Feedback endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.schemas.feedback import FeedbackInviteOut, FeedbackOut, FeedbackSubmission
from app.services import feedback as svc

router = APIRouter(tags=["feedback"])


def _require_case(case_id: str, db: Session) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    return case


@router.post(
    "/cases/{case_id}/trigger-discharge",
    response_model=FeedbackInviteOut,
    status_code=status.HTTP_201_CREATED,
)
def trigger_discharge(case_id: str, db: Session = Depends(get_db)) -> FeedbackInviteOut:
    """Manual stand-in for the 'days later' scheduler: discharge + send feedback link."""
    case = _require_case(case_id, db)
    try:
        return svc.trigger_discharge(db, case)
    except svc.DischargeNotAllowed as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get("/cases/{case_id}/feedback-invite", response_model=FeedbackInviteOut)
def get_feedback_invite(case_id: str, db: Session = Depends(get_db)) -> FeedbackInviteOut:
    _require_case(case_id, db)
    invite = svc.get_invite(db, case_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no feedback invite — trigger discharge first")
    return invite


@router.get("/cases/{case_id}/feedback", response_model=FeedbackOut)
def get_feedback(case_id: str, db: Session = Depends(get_db)) -> FeedbackOut:
    _require_case(case_id, db)
    feedback = svc.get_feedback(db, case_id)
    if feedback is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no feedback submitted for this case")
    return feedback


@router.post(
    "/cases/{case_id}/feedback",
    response_model=FeedbackOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_feedback(
    case_id: str, payload: FeedbackSubmission, db: Session = Depends(get_db)
) -> FeedbackOut:
    _require_case(case_id, db)
    try:
        return svc.submit_feedback(
            db,
            case_id=case_id,
            token=payload.token,
            wait_time_tag=payload.wait_time_tag,
            staff_behavior_tag=payload.staff_behavior_tag,
            cleanliness_tag=payload.cleanliness_tag,
            billing_tag=payload.billing_tag,
            ready_as_shown_tag=payload.ready_as_shown_tag,
        )
    except svc.FeedbackAlreadySubmitted:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "feedback already submitted for this case (rejected by the DB unique constraint on case_id)",
        )
    except svc.FeedbackNotAllowed as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
