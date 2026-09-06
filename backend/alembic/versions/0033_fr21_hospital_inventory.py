"""FR-21: `hospital_inventory_items` + `hospital_inventory_movements` tables.

A real table, not another JSON blob like `hospitals.blood_stock_by_group` —
inventory items need per-item metadata (unit, low-stock threshold) and a
movement history. Movements mirror `hospital_sync_events`'s "every change is
an audited row" pattern.

Revision ID: 0033_fr21_hospital_inventory
Revises: 0032_fr20_staff_attendance
Create Date: 2026-09-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0033_fr21_hospital_inventory"
down_revision: Union[str, None] = "0032_fr20_staff_attendance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hospital_inventory_items",
        sa.Column("item_id", sa.String(length=36), primary_key=True),
        sa.Column("hospital_id", sa.String(length=32), sa.ForeignKey("hospitals.hospital_id"), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("quantity_on_hand", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=True),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_hospital_inventory_items_hospital_id", "hospital_inventory_items", ["hospital_id"])

    op.create_table(
        "hospital_inventory_movements",
        sa.Column("movement_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "item_id", sa.String(length=36), sa.ForeignKey("hospital_inventory_items.item_id"), nullable=False
        ),
        sa.Column("hospital_id", sa.String(length=32), sa.ForeignKey("hospitals.hospital_id"), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_hospital_inventory_movements_item_id", "hospital_inventory_movements", ["item_id"])


def downgrade() -> None:
    op.drop_index("ix_hospital_inventory_movements_item_id", table_name="hospital_inventory_movements")
    op.drop_table("hospital_inventory_movements")
    op.drop_index("ix_hospital_inventory_items_hospital_id", table_name="hospital_inventory_items")
    op.drop_table("hospital_inventory_items")
