"""FR-17 endpoints: hospital-defined bed/room categories beyond general+ICU."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.schemas.bed_category import BedCategoryOut, BedCategoryUpsertRequest, CapacitySnapshot
from app.services import bed_categories as svc
from app.services.access import require_hospital_scope
from app.services.auth_deps import get_principal, require_role
from app.services.security import Principal

router = APIRouter(tags=["bed-categories"])


@router.get("/hospitals/{hospital_id}/bed-categories", response_model=list[BedCategoryOut])
def list_bed_categories(
    hospital_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[BedCategoryOut]:
    require_hospital_scope(principal, hospital_id)
    return svc.list_for_hospital(db, hospital_id)


@router.get("/hospitals/{hospital_id}/bed-categories/snapshot", response_model=CapacitySnapshot)
def bed_category_snapshot(
    hospital_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> CapacitySnapshot:
    require_hospital_scope(principal, hospital_id)
    try:
        return svc.capacity_snapshot(db, hospital_id)
    except svc.HospitalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.put("/hospitals/{hospital_id}/bed-categories/{category_code}", response_model=BedCategoryOut)
def upsert_bed_category(
    hospital_id: str,
    category_code: str,
    payload: BedCategoryUpsertRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> BedCategoryOut:
    require_hospital_scope(principal, hospital_id)
    try:
        return svc.upsert_category(
            db, hospital_id, category_code, label=payload.label, total_beds=payload.total_beds
        )
    except svc.HospitalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get(
    "/bed-categories",
    response_model=list[BedCategoryOut],
    dependencies=[Depends(require_role(Role.admin, Role.control_room))],
)
def all_bed_categories(db: Session = Depends(get_db)) -> list[BedCategoryOut]:
    """Admin/control_room view across every hospital (mirrors /blood-bank-holds)."""
    return svc.list_all(db)
