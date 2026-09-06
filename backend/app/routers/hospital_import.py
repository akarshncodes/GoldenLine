"""FR-22 endpoints: one-time rule-based fuzzy import (CSV upload or a Google
Sheet) into patients/hospital_staff/hospital_inventory_items/bed_categories.

Two-step preview/confirm flow — nothing is ever auto-committed. Hospital-
scoped (receptionist's own hospital, or admin): this is meant as a
self-service bootstrap tool a hospital can run itself, not an admin-only
operation, same reasoning as FR-16's sync-tier endpoints.
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.import_session import ImportSession
from app.schemas.hospital_import import (
    CommitImportRequest,
    CommitResultOut,
    MatchReportOut,
    SheetImportRequest,
)
from app.services import hospital_import as svc
from app.services.access import require_hospital_scope
from app.services.auth_deps import get_principal
from app.services.security import Principal

router = APIRouter(tags=["hospital-import"])


def _require_session(hospital_id: str, import_session_id: str, principal: Principal, db: Session) -> ImportSession:
    session = svc.get_session(db, import_session_id)
    if session is None or session.hospital_id != hospital_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"import session '{import_session_id}' not found")
    require_hospital_scope(principal, session.hospital_id)
    return session


@router.post("/hospitals/{hospital_id}/import/preview-file", response_model=MatchReportOut)
async def preview_file(
    hospital_id: str,
    target_table: str = Form(...),
    file: UploadFile = File(...),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> MatchReportOut:
    require_hospital_scope(principal, hospital_id)
    raw_bytes = await file.read()
    csv_text = raw_bytes.decode("utf-8", errors="replace")
    try:
        session = svc.preview_from_csv_text(
            db, hospital_id=hospital_id, target_table=target_table, csv_text=csv_text, actor=principal.user_id
        )
    except svc.HospitalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except (svc.InvalidImportFile, svc.UnknownTargetTable, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return svc.match_report(session)


@router.post("/hospitals/{hospital_id}/import/preview-sheet", response_model=MatchReportOut)
def preview_sheet(
    hospital_id: str,
    payload: SheetImportRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> MatchReportOut:
    require_hospital_scope(principal, hospital_id)
    try:
        session = svc.preview_from_sheet(
            db, hospital_id=hospital_id, target_table=payload.target_table,
            sheet_url=payload.sheet_url, actor=principal.user_id,
        )
    except svc.HospitalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except (svc.InvalidImportFile, svc.UnknownTargetTable, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return svc.match_report(session)


@router.get("/hospitals/{hospital_id}/import/{import_session_id}", response_model=MatchReportOut)
def get_preview(
    hospital_id: str, import_session_id: str,
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
) -> MatchReportOut:
    session = _require_session(hospital_id, import_session_id, principal, db)
    return svc.match_report(session)


@router.post("/hospitals/{hospital_id}/import/{import_session_id}/commit", response_model=CommitResultOut)
def commit(
    hospital_id: str,
    import_session_id: str,
    payload: CommitImportRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> CommitResultOut:
    _require_session(hospital_id, import_session_id, principal, db)
    try:
        return svc.commit_import(
            db, import_session_id, column_mapping=payload.column_mapping, actor=principal.user_id
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.delete("/hospitals/{hospital_id}/import/{import_session_id}")
def discard(
    hospital_id: str, import_session_id: str,
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
) -> dict:
    _require_session(hospital_id, import_session_id, principal, db)
    svc.discard_session(db, import_session_id)
    return {"discarded": True}
