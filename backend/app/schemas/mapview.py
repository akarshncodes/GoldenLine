"""Map view: read-only ambulance positions for the admin/control-room overview map.

Not a new domain concept — just a projection over the existing FAKE_AMBULANCES
mock fleet (app/services/ambulance.py) and whichever case a helper is currently
working, using the case's live gps fields exactly as FR-2 ranking already does.
"""
from pydantic import BaseModel


class AmbulanceOut(BaseModel):
    ambulance_id: str
    vehicle_number: str
    helper_user_id: str
    base_latitude: float
    base_longitude: float
    # "idle" (no active case, shown at its base pin — not live-tracked while
    # off dispatch) | "en_route_to_pickup" (active case, no hospital chosen
    # yet) | "en_route_to_hospital" (active case, hospital selected/bed
    # locked). Derived from existing case/assessment data, not a stored field.
    status: str
    case_id: str | None = None
    current_latitude: float | None = None
    current_longitude: float | None = None
    # True when Control Room's existing FR-10 anomaly check (stale/missing
    # GPS on this ambulance's in-transit case) is currently escalated and
    # unresolved — surfaces an already-detected problem on the map instead of
    # duplicating the detection logic.
    has_stale_gps_flag: bool = False
