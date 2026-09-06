"""FR-6 endpoints: the hospital receptionist's prep dashboard + confirm action."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.models.prep import PrepActionStatus
from app.schemas.prep import ConfirmPrepActionRequest, PrepActionListOut, PrepActionOut
from app.services import prep as svc

router = APIRouter(tags=["prep"])


@router.get("/cases/{case_id}/prep-actions", response_model=PrepActionListOut)
def list_prep_actions(case_id: str, db: Session = Depends(get_db)) -> PrepActionListOut:
    """Hospital dashboard read — every prep action for the case, split by status."""
    if db.get(Case, case_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    actions = svc.list_for_case(db, case_id)
    return PrepActionListOut(
        case_id=case_id,
        pending=[PrepActionOut.model_validate(a) for a in actions if a.status == PrepActionStatus.pending],
        confirmed=[PrepActionOut.model_validate(a) for a in actions if a.status == PrepActionStatus.confirmed],
    )


@router.post("/prep-actions/{prep_action_id}/confirm", response_model=PrepActionOut)
def confirm_prep_action(
    prep_action_id: str, payload: ConfirmPrepActionRequest, db: Session = Depends(get_db)
) -> PrepActionOut:
    """The explicit receptionist tap. The only path that sets status='confirmed'."""
    try:
        return svc.confirm(db, prep_action_id, confirmed_by=payload.receptionist_id)
    except svc.PrepActionNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"prep action '{prep_action_id}' not found")
    except svc.PrepActionAlreadyConfirmed:
        raise HTTPException(status.HTTP_409_CONFLICT, "prep action is already confirmed")
