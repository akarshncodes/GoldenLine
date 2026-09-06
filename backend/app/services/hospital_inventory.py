"""FR-21 Medical Resource/Inventory."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.models.hospital_inventory import (
    HospitalInventoryItem,
    HospitalInventoryMovement,
    InventoryCategory,
    MovementReason,
)


class HospitalNotFound(Exception):
    pass


class ItemNotFound(Exception):
    pass


def create_item(
    db: Session,
    *,
    hospital_id: str,
    item_name: str,
    category: InventoryCategory,
    unit: str,
    quantity_on_hand: int = 0,
    low_stock_threshold: int | None = None,
    actor: str | None = None,
) -> HospitalInventoryItem:
    if db.get(Hospital, hospital_id) is None:
        raise HospitalNotFound(f"hospital '{hospital_id}' does not exist")
    item = HospitalInventoryItem(
        hospital_id=hospital_id,
        item_name=item_name,
        category=category,
        unit=unit,
        quantity_on_hand=max(0, quantity_on_hand),
        low_stock_threshold=low_stock_threshold,
        updated_by=actor,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def list_for_hospital(db: Session, hospital_id: str) -> list[HospitalInventoryItem]:
    return list(
        db.scalars(
            select(HospitalInventoryItem)
            .where(HospitalInventoryItem.hospital_id == hospital_id)
            .order_by(HospitalInventoryItem.item_name)
        )
    )


def list_all(db: Session) -> list[HospitalInventoryItem]:
    return list(
        db.scalars(
            select(HospitalInventoryItem).order_by(
                HospitalInventoryItem.hospital_id, HospitalInventoryItem.item_name
            )
        )
    )


def get(db: Session, item_id: str) -> HospitalInventoryItem | None:
    return db.get(HospitalInventoryItem, item_id)


def low_stock_items(db: Session, hospital_id: str) -> list[HospitalInventoryItem]:
    return [item for item in list_for_hospital(db, hospital_id) if item.is_low_stock]


def adjust_quantity(
    db: Session, item_id: str, *, delta: int, reason: MovementReason, actor: str
) -> HospitalInventoryItem:
    """Floors at 0 (mirrors hospital_sync.apply_bed_counts's floor), writes an
    audited movement row for every change — same "every write is a row"
    pattern as hospital_sync_events."""
    item = db.get(HospitalInventoryItem, item_id)
    if item is None:
        raise ItemNotFound(f"inventory item '{item_id}' does not exist")

    before = item.quantity_on_hand
    item.quantity_on_hand = max(0, before + delta)
    item.updated_by = actor
    actual_delta = item.quantity_on_hand - before

    db.add(
        HospitalInventoryMovement(
            item_id=item.item_id, hospital_id=item.hospital_id,
            delta=actual_delta, reason=reason, actor=actor,
        )
    )
    db.commit()
    db.refresh(item)
    return item


def movements_for_item(db: Session, item_id: str) -> list[HospitalInventoryMovement]:
    return list(
        db.scalars(
            select(HospitalInventoryMovement)
            .where(HospitalInventoryMovement.item_id == item_id)
            .order_by(HospitalInventoryMovement.created_at.desc())
        )
    )
