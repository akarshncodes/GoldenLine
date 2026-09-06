"""Live ambulance tracking: which ambulance is assigned to a case (identity +
live position), and Control Room's stale-GPS anomaly surfaced on the fleet map.

Not an FR-numbered phase — a standalone post-expansion enhancement request
(family couldn't see which ambulance was coming or where it was; the fleet
map only distinguished idle/dispatched, not the finer role the user wanted).
"""
from datetime import datetime, timedelta, timezone

from tests.helpers import confirm_hospital, path_a_sos

BENGALURU = {"latitude": 12.97, "longitude": 77.59}
DINDIGUL = {"latitude": 10.3673, "longitude": 77.9803}


def _path_b_case(client, helper_id="HLP-001") -> str:
    return client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 55, "gender": "male"},
            "helper_id": helper_id,
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]


# --------------------------------------------------------------- GET .../ambulance
def test_path_a_case_resolves_its_dispatched_ambulance(client):
    res = path_a_sos(client, gps=DINDIGUL)
    case = res.json()["case"]
    cid, helper_id = case["case_id"], case["helper_id"]

    amb = client.get(f"/cases/{cid}/ambulance")
    assert amb.status_code == 200, amb.text
    body = amb.json()
    assert body["vehicle_number"]
    assert body["driver_name"]
    assert "driver_phone" not in body  # deliberately not exposed
    # confirms it's really THIS case's ambulance, not an arbitrary one
    from app.services.ambulance import get_ambulance_for_helper
    expected = get_ambulance_for_helper(helper_id)
    assert body["ambulance_id"] == expected.id


def test_path_b_case_also_resolves_an_ambulance_via_helper_id(client):
    """Path B never sets dispatched_ambulance_id — resolution must go through
    helper_id, not that column, or this would 404."""
    cid = _path_b_case(client, helper_id="HLP-002")
    res = client.get(f"/cases/{cid}/ambulance")
    assert res.status_code == 200, res.text
    assert res.json()["vehicle_number"]


def test_ambulance_position_is_the_case_live_gps(client):
    cid = _path_b_case(client, helper_id="HLP-003")
    before = client.get(f"/cases/{cid}/ambulance").json()
    assert before["latitude"] == BENGALURU["latitude"]
    assert before["longitude"] == BENGALURU["longitude"]

    client.post(
        f"/cases/{cid}/helper-location",
        json={"helper_id": "HLP-003", "gps": {"latitude": 12.99, "longitude": 77.60}},
    )
    after = client.get(f"/cases/{cid}/ambulance").json()
    assert after["latitude"] == 12.99
    assert after["longitude"] == 77.60


def test_unknown_case_404s(client):
    assert client.get("/cases/does-not-exist/ambulance").status_code == 404


def test_family_can_see_their_own_cases_ambulance(client_factory):
    """Case-access scoping (require_case_access) applies here exactly as it
    does to every other /cases/{id}/* sub-resource — no new privacy surface.

    Needs a REAL family session (Bearer token), not just an OTP id in the SOS
    body — otherwise the resulting case's family_user_id is never tied to this
    caller, and require_case_access's family branch can't match anything.
    """
    family = client_factory(None)
    req = family.post("/otp/request", json={"phone_number": "9876543211"}).json()
    verify = family.post(
        "/otp/verify", json={"otp_verification_id": req["otp_verification_id"], "code": req["dev_code"]}
    ).json()
    family.headers["Authorization"] = f"Bearer {verify['access_token']}"

    res = family.post(
        "/cases/sos",
        json={
            "family_phone_number": "9876543211",
            "family_gps": DINDIGUL,
            "otp_verification_id": verify["otp_verification_id"],
        },
    )
    assert res.status_code == 201, res.text
    cid = res.json()["case"]["case_id"]

    amb = family.get(f"/cases/{cid}/ambulance")
    assert amb.status_code == 200, amb.text


# --------------------------------------------------------------- stale-GPS on the map
def test_stale_gps_flag_surfaces_on_the_fleet_map(client, db_session):
    from app.models.case import Case

    cid = _path_b_case(client, helper_id="HLP-004")
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    confirm_hospital(client, cid, helper_id="HLP-004")

    case = db_session.get(Case, cid)
    case.gps_timestamp = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=20)
    db_session.commit()

    client.post("/control-room/scan")

    ambulances = client.get("/ambulances").json()
    mine = next(a for a in ambulances if a["helper_user_id"] == "HLP-004")
    assert mine["has_stale_gps_flag"] is True

    other = next(a for a in ambulances if a["helper_user_id"] != "HLP-004")
    assert other["has_stale_gps_flag"] is False
