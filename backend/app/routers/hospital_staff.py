"""FR-19 endpoints: hospital doctor/staff roster + on-duty status."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.hospital_staff import HospitalStaffMember
from app.schemas.hospital_staff import OnDutyStatusUpdate, StaffCreateRequest, StaffOut
from app.services import hospital_staff as svc
from app.services.access import require_hospital_scope
from app.services.auth_deps import get_principal, require_role
from app.services.security import Principal

router = APIRouter(tags=["hospital-staff"])


def _require_staff(staff_id: str, db: Session) -> HospitalStaffMember:
    staff = svc.get(db, staff_id)
    if staff is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"staff '{staff_id}' does not exist")
    return staff


@router.post("/hospitals/{hospital_id}/staff", response_model=StaffOut)
def create_staff(
    hospital_id: str,
    payload: StaffCreateRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> StaffOut:
    require_hospital_scope(principal, hospital_id)
    try:
        return svc.create_staff(
            db,
            hospital_id=hospital_id,
            full_name=payload.full_name,
            staff_category=payload.staff_category,
            specialty=payload.specialty,
            phone_number=payload.phone_number,
            created_by=principal.user_id,
        )
    except svc.HospitalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get("/hospitals/{hospital_id}/staff", response_model=list[StaffOut])
def list_hospital_staff(
    hospital_id: str,
    include_inactive: bool = Query(default=False),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[StaffOut]:
    require_hospital_scope(principal, hospital_id)
    return svc.list_for_hospital(db, hospital_id, include_inactive=include_inactive)


@router.get(
    "/staff",
    response_model=list[StaffOut],
    dependencies=[Depends(require_role(Role.admin, Role.control_room))],
)
def all_staff(include_inactive: bool = Query(default=False), db: Session = Depends(get_db)) -> list[StaffOut]:
    """Admin/control_room unscoped view across every hospital (mirrors /patients)."""
    return svc.list_all(db, include_inactive=include_inactive)


@router.patch("/staff/{staff_id}/on-duty-status", response_model=StaffOut)
def update_on_duty_status(
    staff_id: str,
    payload: OnDutyStatusUpdate,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> StaffOut:
    staff = _require_staff(staff_id, db)
    require_hospital_scope(principal, staff.hospital_id)
    return svc.set_on_duty_status(db, staff_id, payload.on_duty_status)


@router.delete("/staff/{staff_id}", response_model=StaffOut)
def deactivate_staff(
    staff_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> StaffOut:
    staff = _require_staff(staff_id, db)
    require_hospital_scope(principal, staff.hospital_id)
    return svc.deactivate(db, staff_id)
