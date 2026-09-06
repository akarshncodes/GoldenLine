"""Mock ambulance dispatch for FR-0 Path A.

There is no real ambulance registry or live tracking yet, so we just pick the
nearest vehicle from a small hardcoded list. FR-0 item 5: there is deliberately
NO self-transport fallback — if there is no registered ambulance, the SOS fails.

2026-09-05: 20 ambulances, all based around Dindigul, Tamil Nadu (this demo's
single-city scope) — TN-57 is Dindigul's real RTO code. Names/plates are
invented; only the fact that they're scattered around real Dindigul
coordinates is meaningful (see memory/dindigul-real-data.md).
"""
from dataclasses import dataclass

from app.services.geo import haversine_km


@dataclass(frozen=True)
class FakeAmbulance:
    id: str
    vehicle_number: str
    driver_name: str
    driver_phone: str
    base_latitude: float
    base_longitude: float
    # The helper (not the driver) who rides along and works the case in the
    # console — a real 108-style dispatch sends both people together, so the
    # case's helper is known the instant this ambulance is picked, with no
    # separate "claim this case" step. Maps to a seeded `users` account
    # (see app/services/user_seed.py).
    helper_user_id: str


# Stand-in for a real "registered ambulance app" fleet — all based in Dindigul.
FAKE_AMBULANCES: list[FakeAmbulance] = [
    FakeAmbulance("AMB-001", "TN57AB1001", "Murugan K", "9600000001", 10.3690, 77.9810, "HLP-001"),
    FakeAmbulance("AMB-002", "TN57AB1002", "Karthik S", "9600000002", 10.3705, 77.9850, "HLP-002"),
    FakeAmbulance("AMB-003", "TN57AB1003", "Ramesh Kumar", "9600000003", 10.3620, 77.9870, "HLP-003"),
    FakeAmbulance("AMB-004", "TN57AB1004", "Senthil Kumar", "9600000004", 10.3660, 77.9755, "HLP-004"),
    FakeAmbulance("AMB-005", "TN57AB1005", "Muthu Vel", "9600000005", 10.3715, 77.9790, "HLP-005"),
    FakeAmbulance("AMB-006", "TN57AB1006", "Pandiyan R", "9600000006", 10.3680, 77.9765, "HLP-006"),
    FakeAmbulance("AMB-007", "TN57AB1007", "Rajendran M", "9600000007", 10.3665, 77.9825, "HLP-007"),
    FakeAmbulance("AMB-008", "TN57AB1008", "Saravanan P", "9600000008", 10.3520, 77.9880, "HLP-008"),
    FakeAmbulance("AMB-009", "TN57AB1009", "Kannan S", "9600000009", 10.3730, 77.9800, "HLP-009"),
    FakeAmbulance("AMB-010", "TN57AB1010", "Manikandan V", "9600000010", 10.3708, 77.9848, "HLP-010"),
    FakeAmbulance("AMB-011", "TN57AB1011", "Velmurugan", "9600000011", 10.3745, 77.9770, "HLP-011"),
    FakeAmbulance("AMB-012", "TN57AB1012", "Chandran K", "9600000012", 10.3675, 77.9795, "HLP-012"),
    FakeAmbulance("AMB-013", "TN57AB1013", "Anbu Selvan", "9600000013", 10.3600, 77.9950, "HLP-013"),
    FakeAmbulance("AMB-014", "TN57AB1014", "Ilango R", "9600000014", 10.3690, 77.9835, "HLP-014"),
    FakeAmbulance("AMB-015", "TN57AB1015", "Sivakumar T", "9600000015", 10.3702, 77.9790, "HLP-015"),
    FakeAmbulance("AMB-016", "TN57AB1016", "Palani Samy", "9600000016", 10.3712, 77.9805, "HLP-016"),
    FakeAmbulance("AMB-017", "TN57AB1017", "Ganesan M", "9600000017", 10.3695, 77.9798, "HLP-017"),
    FakeAmbulance("AMB-018", "TN57AB1018", "Balaji R", "9600000018", 10.3610, 77.9700, "HLP-018"),
    FakeAmbulance("AMB-019", "TN57AB1019", "Murali Dharan", "9600000019", 10.3688, 77.9832, "HLP-019"),
    FakeAmbulance("AMB-020", "TN57AB1020", "Selva Kumar", "9600000020", 10.3699, 77.9788, "HLP-020"),
]


class NoAmbulanceAvailable(Exception):
    """No registered ambulance could be dispatched. No self-transport fallback exists."""


def find_nearest_ambulance(latitude: float, longitude: float) -> tuple[FakeAmbulance, float]:
    """Return (ambulance, distance_km) for the nearest fake ambulance."""
    if not FAKE_AMBULANCES:
        raise NoAmbulanceAvailable()
    nearest = min(
        FAKE_AMBULANCES,
        key=lambda amb: haversine_km(latitude, longitude, amb.base_latitude, amb.base_longitude),
    )
    distance = haversine_km(latitude, longitude, nearest.base_latitude, nearest.base_longitude)
    return nearest, round(distance, 2)


_BY_ID = {amb.id: amb for amb in FAKE_AMBULANCES}
_BY_HELPER = {amb.helper_user_id: amb for amb in FAKE_AMBULANCES}


def get_ambulance_by_id(ambulance_id: str) -> FakeAmbulance | None:
    return _BY_ID.get(ambulance_id)


def get_ambulance_for_helper(helper_user_id: str) -> FakeAmbulance | None:
    """The 1:1 ambulance<->helper mapping (see FakeAmbulance.helper_user_id)
    resolves an ambulance for EITHER creation path: Path A also sets
    `Case.dispatched_ambulance_id` directly, but Path B never does (the helper
    self-starts the case, no mock-dispatch matching runs) — so `helper_id` is
    the one field guaranteed to be set once a case exists via either path."""
    return _BY_HELPER.get(helper_user_id)
