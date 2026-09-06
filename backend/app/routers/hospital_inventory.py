"""FR-21 endpoints: hospital medical resource/inventory."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.hospital_inventory import HospitalInventoryItem
from app.schemas.hospital_inventory import (
    AdjustQuantityRequest,
    InventoryItemCreateRequest,
    InventoryItemOut,
    MovementOut,
)
from app.services import hospital_inventory as svc
from app.services.access import require_hospital_scope
from app.services.auth_deps import get_principal, require_role
from app.services.security import Principal

router = APIRouter(tags=["hospital-inventory"])


def _require_item(item_id: str, db: Session) -> HospitalInventoryItem:
    item = svc.get(db, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"inventory item '{item_id}' does not exist")
    return item


@router.post("/hospitals/{hospital_id}/inventory", response_model=InventoryItemOut)
def create_item(
    hospital_id: str,
    payload: InventoryItemCreateRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> InventoryItemOut:
    require_hospital_scope(principal, hospital_id)
    try:
        return svc.create_item(
            db,
            hospital_id=hospital_id,
            item_name=payload.item_name,
            category=payload.category,
            unit=payload.unit,
            quantity_on_hand=payload.quantity_on_hand,
            low_stock_threshold=payload.low_stock_threshold,
            actor=principal.user_id,
        )
    except svc.HospitalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get("/hospitals/{hospital_id}/inventory", response_model=list[InventoryItemOut])
def list_hospital_inventory(
    hospital_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[InventoryItemOut]:
    require_hospital_scope(principal, hospital_id)
    return svc.list_for_hospital(db, hospital_id)


@router.get(
    "/inventory",
    response_model=list[InventoryItemOut],
    dependencies=[Depends(require_role(Role.admin, Role.control_room))],
)
def all_inventory(db: Session = Depends(get_db)) -> list[InventoryItemOut]:
    """Admin/control_room unscoped view across every hospital (mirrors /staff, /patients)."""
    return svc.list_all(db)


@router.post("/inventory/{item_id}/adjust", response_model=InventoryItemOut)
def adjust_quantity(
    item_id: str,
    payload: AdjustQuantityRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> InventoryItemOut:
    item = _require_item(item_id, db)
    require_hospital_scope(principal, item.hospital_id)
    return svc.adjust_quantity(db, item_id, delta=payload.delta, reason=payload.reason, actor=principal.user_id)


@router.get("/inventory/{item_id}/movements", response_model=list[MovementOut])
def item_movements(
    item_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[MovementOut]:
    item = _require_item(item_id, db)
    require_hospital_scope(principal, item.hospital_id)
    return svc.movements_for_item(db, item_id)
