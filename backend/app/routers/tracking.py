"""FR-9: the single read-only tracking endpoint. GET only — no writes, ever."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.schemas.tracking import TrackingExpired, TrackingLinkOut, TrackingView
from app.services import tracking as svc
from app.services.auth_deps import case_access

router = APIRouter(tags=["tracking"])


@router.get("/cases/{case_id}/tracking-link", response_model=TrackingLinkOut)
def get_case_tracking_link(case: Case = Depends(case_access), db: Session = Depends(get_db)) -> TrackingLinkOut:
    """For the console (helper/admin) to hand the family their tracking link —
    the SMS send is a stub, so this is how a tester (or a real operator,
    until a real SMS gateway exists) actually gets the link. Path A cases
    never get a token (see tracking.py's create_for_path_b_case) -> 404.
    """
    row = svc.get_token_row(db, case.case_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no tracking link for this case")
    return TrackingLinkOut(token=row.token, expires_at=row.token_expires_at)


@router.get(
    "/track/{token}",
    response_model=TrackingView,
    responses={410: {"model": TrackingExpired}, 404: {"description": "not found"}},
)
def track_case(token: str, db: Session = Depends(get_db)):
    """Family tracking page. Scoped to exactly one case by an unguessable token.

    Unknown token -> 404 (no hint that other tokens exist).
    Past expiry   -> 410 with a plain 'This link has expired' (no case data).
    """
    try:
        view = svc.get_tracking_view(db, token)
    except svc.TokenExpired:
        return JSONResponse(status_code=status.HTTP_410_GONE, content=TrackingExpired().model_dump())

    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    return view
