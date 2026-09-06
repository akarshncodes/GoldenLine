"""Pydantic schemas for exposing an individual ambulance's identity/position
to the case it's currently assigned to. Deliberately excludes the driver's
phone number — a family-facing decision, not a technical one (name + vehicle
number is enough to know who's coming, without a direct-call surface)."""
from datetime import datetime

from pydantic import BaseModel


class AmbulanceSummaryOut(BaseModel):
    ambulance_id: str
    vehicle_number: str
    driver_name: str
    # the SAME case.gps_latitude/longitude/gps_timestamp FR-2 ranking already
    # reads — an ambulance's "current" position is just its assigned case's
    # live GPS, no separate tracking mechanism. Null until the helper's device
    # has reported at least once (fresh Path A case, pre-dispatch-confirmation).
    latitude: float | None
    longitude: float | None
    gps_timestamp: datetime | None
