"""FR-0 Case Creation — both paths."""
from tests.helpers import path_a_sos, verified_otp

DELHI = {"latitude": 28.61, "longitude": 77.20}
MUMBAI = {"latitude": 19.07, "longitude": 72.87}
BENGALURU = {"latitude": 12.97, "longitude": 77.59}


# ---------------------------------------------------------------- Path A --------
def test_path_a_creates_case_with_ambulance_and_no_family_location(client):
    res = path_a_sos(client, gps=DELHI)
    assert res.status_code == 201, res.text
    body = res.json()

    assert body["case"]["creation_path"] == "A"
    assert body["case"]["status"] == "AMBULANCE_DISPATCHED"
    assert body["case"]["family_phone_number"] == "9876543210"

    # some hardcoded ambulance was dispatched (all 20 are Dindigul-based now,
    # so "nearest" isn't meaningfully testable from a far-away GPS point like
    # Delhi — see test_dindigul_local_sos_dispatches_the_closest_ambulance
    # below for a same-city proximity check)
    assert body["dispatched_ambulance"]["id"].startswith("AMB-")
    assert body["case"]["dispatched_ambulance_id"] == body["dispatched_ambulance"]["id"]

    # FR-0 line 85: the family's phone GPS must NOT become the case location
    assert body["case"]["gps_latitude"] is None
    assert body["case"]["gps_longitude"] is None
    assert body["case"]["gps_source"] is None

    # FR-0 line 97: the SOS location is still attached to the case — audit only
    assert body["case"]["sos_trigger_latitude"] == DELHI["latitude"]
    assert body["case"]["sos_trigger_longitude"] == DELHI["longitude"]
    assert body["case"]["sos_trigger_timestamp"] is not None


def test_dindigul_local_sos_dispatches_the_closest_ambulance(client):
    """All 20 mock ambulances are Dindigul-based (app/services/ambulance.py) —
    an SOS from right on top of one of their bases must dispatch that one."""
    res = path_a_sos(client, phone_number="9876500011", gps={"latitude": 10.3745, "longitude": 77.9770})
    assert res.status_code == 201, res.text
    assert res.json()["dispatched_ambulance"]["id"] == "AMB-011"


def test_path_a_location_is_set_only_from_helper_device(client):
    case_id = path_a_sos(client, gps=DELHI).json()["case"]["case_id"]

    res = client.post(
        f"/cases/{case_id}/helper-location",
        json={"helper_id": "HLP-002", "gps": MUMBAI},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["gps_latitude"] == 19.07
    assert body["gps_longitude"] == 72.87
    assert body["gps_source"] == "helper_device"
    assert body["helper_id"] == "HLP-002"
    # the audit-only SOS coords are untouched by the helper location update
    assert body["sos_trigger_latitude"] == DELHI["latitude"]


def test_path_a_rejects_invalid_family_phone(client):
    otp_id = verified_otp(client, "9876543210")
    res = client.post(
        "/cases/sos",
        json={"family_phone_number": "12345", "family_gps": DELHI, "otp_verification_id": otp_id},
    )
    assert res.status_code == 422


# ---------------------------------------------------------------- Path B --------
def _path_b_body(**overrides):
    body = {
        "next_of_kin_phone_number": "9123456780",
        "patient": {"name": "Asha", "approx_age": 40, "gender": "female"},
        "helper_id": "HLP-001",
        "helper_gps": BENGALURU,
    }
    body.update(overrides)
    return body


def test_path_b_rejected_when_next_of_kin_missing(client):
    body = _path_b_body()
    del body["next_of_kin_phone_number"]
    res = client.post("/cases", json=body)
    assert res.status_code == 422
    assert "next_of_kin_phone_number" in res.text


def test_path_b_rejected_when_next_of_kin_invalid(client):
    # starts with 1 -> fails ^[6-9]\d{9}$
    res = client.post("/cases", json=_path_b_body(next_of_kin_phone_number="1234567890"))
    assert res.status_code == 422
    assert "next_of_kin_phone_number" in res.text


def test_path_b_rejected_when_patient_details_missing(client):
    body = _path_b_body()
    del body["patient"]
    res = client.post("/cases", json=body)
    assert res.status_code == 422


def test_path_b_succeeds_with_valid_next_of_kin(client):
    res = client.post("/cases", json=_path_b_body())
    assert res.status_code == 201, res.text
    body = res.json()

    assert body["creation_path"] == "B"
    assert body["status"] == "OPEN"
    assert body["next_of_kin_phone_number"] == "9123456780"
    assert body["patient_name"] == "Asha"
    assert body["patient_approx_age"] == 40
    assert body["patient_gender"] == "female"

    # FR-0 item 4: case location comes from the helper device
    assert body["gps_latitude"] == 12.97
    assert body["gps_source"] == "helper_device"
    assert body["family_phone_number"] is None
    # SOS trigger coords are a Path A concept only
    assert body["sos_trigger_latitude"] is None
