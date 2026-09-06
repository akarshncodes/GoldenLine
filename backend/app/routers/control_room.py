"""FR-10 Control Room endpoints.

This is a background/monitoring surface — there is NO chat interface with
families or hospitals here. It exposes:
  * POST /control-room/scan                     — run the 3 checks now (stand-in
                                                   for a real scheduler)
  * GET  /control-room/flags                    — the human's review dashboard
  * GET  /control-room/flags/{id}
  * POST /control-room/flags/{id}/resolve       — the ONLY way to reach 'resolved'
  * PUT  /hospitals/{id}/reported-bed-usage     — a hospital reports its own live
                                                   bed usage (what reconciliation
                                                   observes; FR-16 automates this)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.control_room import FlagType
from app.models.hospital import Hospital
from app.models.hospital_bed_report import HospitalBedReport
from app.schemas.control_room import (
    FlagOut,
    ReportedBedUsageOut,
    ReportedBedUsageRequest,
    ResolveFlagRequest,
    ScanResultOut,
)
from app.services import control_room as svc
from app.services.access import require_hospital_scope
from app.services.auth_deps import require_role
from app.services.security import Principal

router = APIRouter(tags=["control-room"])

# The Control Room is an internal supervisor — only control_room / admin operate it.
_control_room = require_role(Role.control_room, Role.admin)


@router.post("/control-room/scan", response_model=ScanResultOut)
def run_scan(
    principal: Principal = Depends(_control_room),
    db: Session = Depends(get_db),
) -> ScanResultOut:
    """Run anomaly / conflict / reconciliation checks now. Idempotent — a second
    run does not duplicate flags that are still open."""
    result = svc.run_all_checks(db)
    return ScanResultOut(
        anomaly_flag_ids=result.anomaly_flag_ids,
        conflict_flag_ids=result.conflict_flag_ids,
        reconciliation_flag_ids=result.reconciliation_flag_ids,
        total=result.total,
    )


@router.get("/control-room/flags", response_model=list[FlagOut])
def list_flags(
    include_resolved: bool = False,
    flag_type: FlagType | None = None,
    principal: Principal = Depends(_control_room),
    db: Session = Depends(get_db),
) -> list[FlagOut]:
    """The human escalation contact's dashboard: all open/escalated flags,
    newest first. `?include_resolved=true` to see the full history."""
    return svc.list_flags(db, include_resolved=include_resolved, flag_type=flag_type)


@router.get("/control-room/flags/{flag_id}", response_model=FlagOut)
def get_flag(
    flag_id: str,
    principal: Principal = Depends(_control_room),
    db: Session = Depends(get_db),
) -> FlagOut:
    flag = svc.get_flag(db, flag_id)
    if flag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"flag '{flag_id}' does not exist")
    return flag


@router.post("/control-room/flags/{flag_id}/resolve", response_model=FlagOut)
def resolve_flag(
    flag_id: str,
    payload: ResolveFlagRequest,
    principal: Principal = Depends(_control_room),
    db: Session = Depends(get_db),
) -> FlagOut:
    """Explicit human action — the single code path that sets status='resolved'."""
    try:
        return svc.resolve_flag(
            db, flag_id=flag_id, resolved_by=principal.user_id, note=payload.resolution_note
        )
    except svc.FlagError as exc:
        msg = str(exc)
        code = status.HTTP_404_NOT_FOUND if "does not exist" in msg else status.HTTP_409_CONFLICT
        raise HTTPException(code, msg)


@router.put("/hospitals/{hospital_id}/reported-bed-usage", response_model=ReportedBedUsageOut)
def report_bed_usage(
    hospital_id: str,
    payload: ReportedBedUsageRequest,
    principal: Principal = Depends(
        require_role(Role.hospital_receptionist, Role.control_room, Role.admin)
    ),
    db: Session = Depends(get_db),
) -> ReportedBedUsageOut:
    """A hospital reports its own current in-use bed counts. FR-10 reconciliation
    compares this against the platform's active bed locks on the next scan."""
    require_hospital_scope(principal, hospital_id)  # receptionist -> own hospital only
    if db.get(Hospital, hospital_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"hospital '{hospital_id}' does not exist")

    report = db.get(HospitalBedReport, hospital_id)
    if report is None:
        report = HospitalBedReport(hospital_id=hospital_id)
        db.add(report)
    report.reported_general_in_use = payload.reported_general_in_use
    report.reported_icu_in_use = payload.reported_icu_in_use
    report.reported_by = principal.user_id
    report.reported_at = svc._now()
    db.commit()
    db.refresh(report)
    return report
