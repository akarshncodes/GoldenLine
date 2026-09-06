"""FR-16 Hospital Data Sync endpoints.

Tier-specific triggers, a one-tap manual counter, a sync-status read, and an
admin tier-config endpoint. The QR-handoff auto-decrement is NOT here — it is
wired inside `app.services.handoff.scan()` so it can only fire on a real
admission event (FR-7).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.hospital import Hospital
from app.schemas.hospital_sync import (
    ManualAdjustRequest,
    SheetSyncRequest,
    SyncOutcomeOut,
    SyncStatusOut,
    SyncTierUpdate,
)
from app.services import hospital_sync as svc
from app.services.access import require_hospital_scope
from app.services.auth_deps import get_principal, require_role
from app.services.security import Principal

router = APIRouter(tags=["hospital-sync"])


def _outcome(o: svc.SyncOutcome) -> SyncOutcomeOut:
    return SyncOutcomeOut(
        hospital_id=o.hospital_id, source=o.source,
        bed_count_by_type=o.bed_count_by_type, last_synced_at=o.last_synced_at, event=o.event,
    )


def _handle(exc: Exception) -> HTTPException:
    if isinstance(exc, svc.HospitalNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, svc.SyncTierMismatch):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, svc.BadManualAdjust):
        return HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    raise exc


@router.post("/hospitals/{hospital_id}/sync/hms", response_model=SyncOutcomeOut)
def trigger_hms_sync(
    hospital_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> SyncOutcomeOut:
    require_hospital_scope(principal, hospital_id)
    try:
        return _outcome(svc.sync_from_hms(db, hospital_id))
    except (svc.HospitalNotFound, svc.SyncTierMismatch, svc.BadManualAdjust) as exc:
        raise _handle(exc)


@router.post("/hospitals/{hospital_id}/sync/sheet", response_model=SyncOutcomeOut)
def trigger_sheet_sync(
    hospital_id: str,
    payload: SheetSyncRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> SyncOutcomeOut:
    require_hospital_scope(principal, hospital_id)
    try:
        return _outcome(svc.sync_from_sheet(db, hospital_id, payload.sheet_url or ""))
    except (svc.HospitalNotFound, svc.SyncTierMismatch, svc.BadManualAdjust) as exc:
        raise _handle(exc)


@router.post("/hospitals/{hospital_id}/beds/adjust", response_model=SyncOutcomeOut)
def manual_bed_adjust(
    hospital_id: str,
    payload: ManualAdjustRequest,
    principal: Principal = Depends(require_role(Role.hospital_receptionist, Role.admin, Role.control_room)),
    db: Session = Depends(get_db),
) -> SyncOutcomeOut:
    """The hospital receptionist's one-tap ±1 bed counter (manual_counter tier)."""
    require_hospital_scope(principal, hospital_id)
    try:
        return _outcome(
            svc.manual_adjust(
                db, hospital_id, bed_type=payload.bed_type, delta=payload.delta,
                actor=principal.user_id,
            )
        )
    except (svc.HospitalNotFound, svc.SyncTierMismatch, svc.BadManualAdjust) as exc:
        raise _handle(exc)


@router.get("/hospitals/{hospital_id}/sync-status", response_model=SyncStatusOut)
def sync_status(
    hospital_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> SyncStatusOut:
    require_hospital_scope(principal, hospital_id)
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"hospital '{hospital_id}' does not exist")
    return SyncStatusOut(
        hospital_id=hospital.hospital_id,
        hospital_sync_tier=hospital.hospital_sync_tier,
        sheet_url=hospital.sheet_url,
        bed_count_by_type=hospital.bed_count_by_type,
        last_synced_at=hospital.last_synced_at,
        recent_events=svc.recent_events(db, hospital_id),
    )


@router.put("/hospitals/{hospital_id}/sync-tier", response_model=SyncStatusOut)
def set_sync_tier(
    hospital_id: str,
    payload: SyncTierUpdate,
    principal: Principal = Depends(require_role(Role.admin)),
    db: Session = Depends(get_db),
) -> SyncStatusOut:
    """Onboarding/config: put a hospital on a sync tier (admin only)."""
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"hospital '{hospital_id}' does not exist")
    hospital.hospital_sync_tier = payload.hospital_sync_tier
    if payload.sheet_url is not None:
        hospital.sheet_url = payload.sheet_url
    db.commit()
    db.refresh(hospital)
    return SyncStatusOut(
        hospital_id=hospital.hospital_id,
        hospital_sync_tier=hospital.hospital_sync_tier,
        sheet_url=hospital.sheet_url,
        bed_count_by_type=hospital.bed_count_by_type,
        last_synced_at=hospital.last_synced_at,
        recent_events=svc.recent_events(db, hospital_id),
    )
