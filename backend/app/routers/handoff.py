"""FR-7 QR Handoff endpoints: generate (helper), scan (hospital), clinical info."""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.schemas.handoff import ClinicalInfoUpdate, QrPayloadOut, ScanRequest
from app.services import handoff as svc

router = APIRouter(tags=["handoff"])

# Deliberately identical for every failure mode — no data leak about which check failed.
_INVALID_TOKEN_DETAIL = "invalid, expired, or already-used handoff token — no data returned"


def _require_case(case_id: str, db: Session) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    return case


@router.patch("/cases/{case_id}/clinical-info", response_model=dict)
def update_clinical_info(
    case_id: str, payload: ClinicalInfoUpdate, db: Session = Depends(get_db)
) -> dict:
    """Helper records admission-ready data during transit (all fields optional)."""
    case = _require_case(case_id, db)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(case, field, value)
    db.commit()
    db.refresh(case)
    return {
        "case_id": case_id,
        "patient_name": case.patient_name,
        "known_allergies": case.known_allergies,
        "current_medications": case.current_medications,
        "blood_group": case.blood_group,
    }


@router.post(
    "/cases/{case_id}/qr-handoff",
    response_model=QrPayloadOut,
    status_code=status.HTTP_201_CREATED,
)
def generate_qr_handoff(case_id: str, db: Session = Depends(get_db)) -> QrPayloadOut:
    """Helper app, on arrival: mint a short-lived token for the hospital to scan."""
    case = _require_case(case_id, db)
    try:
        payload = svc.generate_token(db, case)
    except svc.HandoffNotReady as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    compact = json.dumps({"case_id": payload.case_id, "token": payload.token}, separators=(",", ":"))
    return QrPayloadOut(
        case_id=payload.case_id,
        token=payload.token,
        expires_at=payload.expires_at,
        qr_payload=compact,
    )


@router.post("/qr-handoff/scan", response_model=dict)
def scan_qr_handoff(payload: ScanRequest, db: Session = Depends(get_db)) -> dict:
    """Hospital device: validate the token and return the full admission bundle."""
    try:
        return svc.scan(
            db,
            case_id=payload.case_id,
            token_value=payload.token,
            scanned_by=payload.scanned_by,
        )
    except svc.InvalidHandoffToken:
        raise HTTPException(status.HTTP_403_FORBIDDEN, _INVALID_TOKEN_DETAIL)
