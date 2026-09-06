"""FR-2 mock hospital dataset (+ FR-16 tiered data sync).

Static seed data standing in for a real hospital registry + live capacity feed.
`distance_km` / `eta_minutes` are treated as pre-computed fields on the hospital
row for this mock — a real routing API fills them later.

FR-16: `live_bed_count` / `live_icu_count` ARE the "bed_count_by_type" structure
the FR-2 ranking step reads from. Every sync tier (HMS API / Google Sheets /
manual counter) and the QR-handoff auto-decrement write here through the single
writer `app.services.hospital_sync.apply_bed_counts` — there is deliberately no
per-tier ranking path.
"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum as SAEnum, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CostTier(str, enum.Enum):
    GOVERNMENT_LOW = "Government-Low"
    PRIVATE_STANDARD = "Private-Standard"
    PRIVATE_PREMIUM = "Private-Premium"


class HospitalSyncTier(str, enum.Enum):
    """FR-16: how a hospital keeps its bed counts current, most→least automated."""
    hms_api = "hms_api"
    google_sheets = "google_sheets"
    manual_counter = "manual_counter"


# Cheapest-appropriate first. Used to order tiers in the ranked list; a scheme
# boost can never move a hospital out of its own tier.
COST_TIER_ORDER: dict[str, int] = {
    CostTier.GOVERNMENT_LOW.value: 0,
    CostTier.PRIVATE_STANDARD.value: 1,
    CostTier.PRIVATE_PREMIUM.value: 2,
}


class Hospital(Base):
    __tablename__ = "hospitals"

    hospital_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    specialties: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    live_bed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    live_icu_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Fixed physical capacity, set once at seed time and never mutated by any
    # admission/discharge/sync write path — the "total" a dashboard should show.
    # `live_bed_count`/`live_icu_count` above keep meaning exactly what they
    # already meant everywhere else (current free-for-new-admission capacity,
    # decremented by every admission path, read by ranking/bed-lock) — nothing
    # about that changes. See app/services/bed_lock.py::HospitalAvailability.
    total_bed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_icu_bed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    eta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[float] = mapped_column(Float, nullable=False)  # 0.0 - 5.0
    cost_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    accepted_schemes: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    # --- FR-4: geo coordinates (used only for the real Google Maps call) ---
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- FR-5: recorded blood stock, units by group e.g. {"O-": 1, "O+": 8} ---
    blood_stock_by_group: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # --- FR-16: tiered data sync ---
    hospital_sync_tier: Mapped[HospitalSyncTier] = mapped_column(
        SAEnum(HospitalSyncTier, native_enum=False, length=16),
        nullable=False,
        default=HospitalSyncTier.manual_counter,
        server_default=HospitalSyncTier.manual_counter.value,
    )
    # only meaningful for the google_sheets tier
    sheet_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # last time bed counts were refreshed, whichever tier did it
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def bed_count_by_type(self) -> dict[str, int]:
        """The one structure FR-2 ranking + FR-3 bed-lock read capacity from.
        Every FR-16 sync tier writes into this (via hospital_sync.apply_bed_counts)."""
        return {"general": self.live_bed_count, "ICU": self.live_icu_count}
