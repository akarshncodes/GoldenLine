"""Pydantic schemas for FR-21 Medical Resource/Inventory."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.hospital_inventory import InventoryCategory, MovementReason


class InventoryItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_name: str = Field(min_length=1, max_length=200)
    category: InventoryCategory
    unit: str = Field(min_length=1, max_length=20)
    quantity_on_hand: int = Field(default=0, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)


class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    hospital_id: str
    item_name: str
    category: InventoryCategory
    unit: str
    quantity_on_hand: int
    low_stock_threshold: int | None
    is_low_stock: bool
    last_updated_at: datetime
    updated_by: str | None


class AdjustQuantityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delta: int
    reason: MovementReason


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    movement_id: str
    item_id: str
    hospital_id: str
    delta: int
    reason: MovementReason
    actor: str | None
    created_at: datetime
