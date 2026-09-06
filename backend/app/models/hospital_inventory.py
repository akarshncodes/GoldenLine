"""FR-21 Medical Resource/Inventory.

A real table, not another JSON blob like `Hospital.blood_stock_by_group` —
inventory items are an open-ended, hospital-defined list needing per-item
metadata (unit, low-stock threshold) and a movement history, the same
reasoning that justified FR-17's `bed_categories` as its own table. Movement
audit mirrors `hospital_sync_events`'s "every change is a row" pattern.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InventoryCategory(str, enum.Enum):
    medicine = "medicine"
    consumable = "consumable"
    equipment = "equipment"
    ppe = "ppe"
    other = "other"


class MovementReason(str, enum.Enum):
    restock = "restock"
    consumed = "consumed"
    correction = "correction"
    import_ = "import"  # 'import' is a Python keyword; the enum VALUE is still "import"


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    """Store the enum *value* (e.g. 'import'), not its name (e.g. 'import_').

    Needed here because SAEnum(native_enum=False) stores the member NAME by
    default (see app/models/assessment.py's identical helper) — without this,
    MovementReason.import_ would be stored as the string 'import_', not
    'import', diverging from every other reason's name==value shape.
    """
    return [member.value for member in enum_cls]


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HospitalInventoryItem(Base):
    __tablename__ = "hospital_inventory_items"

    item_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    hospital_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("hospitals.hospital_id"), nullable=False, index=True
    )
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[InventoryCategory] = mapped_column(
        SAEnum(InventoryCategory, native_enum=False, length=16), nullable=False
    )
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    @property
    def is_low_stock(self) -> bool:
        return self.low_stock_threshold is not None and self.quantity_on_hand <= self.low_stock_threshold


class HospitalInventoryMovement(Base):
    """Audit trail — one row per quantity change, mirrors hospital_sync_events."""
    __tablename__ = "hospital_inventory_movements"

    movement_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hospital_inventory_items.item_id"), nullable=False, index=True
    )
    hospital_id: Mapped[str] = mapped_column(String(32), ForeignKey("hospitals.hospital_id"), nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[MovementReason] = mapped_column(
        SAEnum(MovementReason, native_enum=False, length=16, values_callable=_enum_values), nullable=False
    )
    actor: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
