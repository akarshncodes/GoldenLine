"""FR-11: data-deletion requests + admin review, and a rate-limit-flag review list."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import DeletionStatus, RateLimitFlag, Role
from app.models.case import Case
from app.services import deletion as svc
from app.services.access import require_case_access, require_roles
from app.services.auth_deps import get_principal, require_role
from app.services.security import Principal

router = APIRouter(tags=["privacy"])


class DeletionRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    deletion_request_id: str
    case_id: str
    requested_by: str
    status: DeletionStatus
    requested_at: object
    processed_at: object | None
    processed_by: str | None


class RateLimitFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rate_limit_flag_id: str
    source: str
    source_type: str
    request_count: int
    window_seconds: int
    reviewed: bool
    flagged_at: object


@router.post(
    "/cases/{case_id}/deletion-request",
    response_model=DeletionRequestOut,
    status_code=status.HTTP_201_CREATED,
)
def file_deletion_request(
    case_id: str, request: Request, db: Session = Depends(get_db)
) -> DeletionRequestOut:
    """The case's family/helper (or admin) asks for their personal data to be deleted."""
    principal: Principal = get_principal(request)
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    require_case_access(db, principal, case)
    try:
        return svc.file_request(db, case=case, requested_by=principal.user_id)
    except svc.DeletionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get("/deletion-requests", response_model=list[DeletionRequestOut])
def list_deletion_requests(
    pending_only: bool = False,
    principal: Principal = Depends(require_role(Role.admin, Role.control_room)),
    db: Session = Depends(get_db),
) -> list[DeletionRequestOut]:
    return svc.list_requests(db, pending_only=pending_only)


@router.post("/deletion-requests/{request_id}/process", response_model=DeletionRequestOut)
def process_deletion_request(
    request_id: str,
    principal: Principal = Depends(require_role(Role.admin)),
    db: Session = Depends(get_db),
) -> DeletionRequestOut:
    """Admin-triggered stand-in for the deletion job: scrubs personal fields."""
    try:
        return svc.process_request(db, request_id=request_id, processed_by=principal.user_id)
    except svc.DeletionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get("/rate-limit-flags", response_model=list[RateLimitFlagOut])
def list_rate_limit_flags(
    principal: Principal = Depends(require_role(Role.admin, Role.control_room)),
    db: Session = Depends(get_db),
) -> list[RateLimitFlagOut]:
    return list(db.scalars(select(RateLimitFlag).order_by(RateLimitFlag.flagged_at.desc())))
