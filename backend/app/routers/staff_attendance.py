"""FR-20 endpoints: staff clock-in/clock-out + attendance history."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.staff_attendance import AttendanceOut, ClockInRequest
from app.services import hospital_staff as staff_svc
from app.services import staff_attendance as svc
from app.services.access import require_hospital_scope
from app.services.auth_deps import get_principal
from app.services.security import Principal

router = APIRouter(tags=["staff-attendance"])


def _require_staff_scope(staff_id: str, principal: Principal, db: Session) -> None:
    staff = staff_svc.get(db, staff_id)
    if staff is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"staff '{staff_id}' does not exist")
    require_hospital_scope(principal, staff.hospital_id)


@router.post("/staff/{staff_id}/clock-in", response_model=AttendanceOut)
def clock_in(
    staff_id: str,
    payload: ClockInRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> AttendanceOut:
    _require_staff_scope(staff_id, principal, db)
    try:
        return svc.clock_in(
            db, staff_id, actor=principal.user_id, shift_label=payload.shift_label, notes=payload.notes
        )
    except svc.AlreadyClockedIn as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post("/staff/{staff_id}/clock-out", response_model=AttendanceOut)
def clock_out(
    staff_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> AttendanceOut:
    _require_staff_scope(staff_id, principal, db)
    try:
        return svc.clock_out(db, staff_id, actor=principal.user_id)
    except svc.NotClockedIn as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.get("/staff/{staff_id}/attendance", response_model=list[AttendanceOut])
def staff_attendance_history(
    staff_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[AttendanceOut]:
    _require_staff_scope(staff_id, principal, db)
    return svc.history_for_staff(db, staff_id)


@router.get("/hospitals/{hospital_id}/attendance", response_model=list[AttendanceOut])
def hospital_attendance_history(
    hospital_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[AttendanceOut]:
    require_hospital_scope(principal, hospital_id)
    return svc.history_for_hospital(db, hospital_id)
