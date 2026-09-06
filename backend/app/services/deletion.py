"""FR-11: post-emergency data-deletion requests + admin processing."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import DeletionRequest, DeletionStatus
from app.models.case import Case, CaseStatus
from app.models.tracking import CaseTrackingToken


class DeletionError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def file_request(db: Session, *, case: Case, requested_by: str) -> DeletionRequest:
    if case.status != CaseStatus.DISCHARGED:
        raise DeletionError("deletion can only be requested after the case is closed")
    existing = db.scalar(
        select(DeletionRequest).where(
            DeletionRequest.case_id == case.case_id,
            DeletionRequest.status == DeletionStatus.pending,
        )
    )
    if existing is not None:
        return existing
    row = DeletionRequest(case_id=case.case_id, requested_by=requested_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_requests(db: Session, *, pending_only: bool = False) -> list[DeletionRequest]:
    stmt = select(DeletionRequest).order_by(DeletionRequest.requested_at.desc())
    if pending_only:
        stmt = stmt.where(DeletionRequest.status == DeletionStatus.pending)
    return list(db.scalars(stmt))


def process_request(db: Session, *, request_id: str, processed_by: str) -> DeletionRequest:
    """Admin-triggered. Scrubs the personal fields on the case and closes the request."""
    row = db.get(DeletionRequest, request_id)
    if row is None:
        raise DeletionError("deletion request not found")
    if row.status != DeletionStatus.pending:
        raise DeletionError(f"request already {row.status.value}")

    case = db.get(Case, row.case_id)
    if case is not None:
        case.patient_name = None
        case.known_allergies = None
        case.current_medications = None
        case.blood_group = None
        case.family_phone_number = None
        case.next_of_kin_phone_number = None
        token = db.scalar(
            select(CaseTrackingToken).where(CaseTrackingToken.case_id == case.case_id)
        )
        if token is not None:
            db.delete(token)

    row.status = DeletionStatus.processed
    row.processed_at = _utcnow()
    row.processed_by = processed_by
    db.commit()
    db.refresh(row)
    return row
