"""Map view: GET /ambulances — admin/control-room only, 3-state status shape."""
from tests.helpers import confirm_hospital, path_a_sos

DINDIGUL = {"latitude": 10.3673, "longitude": 77.9803}
_STATUSES = ("idle", "en_route_to_pickup", "en_route_to_hospital")


def test_requires_admin_or_control_room(client_factory):
    helper = client_factory("HLP-001")
    assert helper.get("/ambulances").status_code == 403

    family = client_factory(None)  # no auth at all
    assert family.get("/ambulances").status_code == 401


def test_control_room_can_list_ambulances(client_factory):
    cr = client_factory("control-room")
    res = cr.get("/ambulances")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 20  # FAKE_AMBULANCES fleet size
    for amb in body:
        assert amb["status"] in _STATUSES
        assert amb["has_stale_gps_flag"] is False  # nothing flagged in a fresh DB
        if amb["status"] == "idle":
            assert amb["case_id"] is None
            assert amb["current_latitude"] is None


def test_dispatched_ambulance_shows_case_live_location_and_pickup_status(client):
    res = path_a_sos(client, gps=DINDIGUL)
    assert res.status_code == 201, res.text
    case = res.json()["case"]
    helper_id = case["helper_id"]
    assert helper_id, "Path A should auto-assign a helper/ambulance"

    ambulances = client.get("/ambulances").json()
    mine = next(a for a in ambulances if a["helper_user_id"] == helper_id)
    # no hospital selected yet -> still on the way to the patient, not the hospital
    assert mine["status"] == "en_route_to_pickup"
    assert mine["case_id"] == case["case_id"]
    assert mine["current_latitude"] == case["gps_latitude"]
    assert mine["current_longitude"] == case["gps_longitude"]


def test_ambulance_status_flips_to_en_route_to_hospital_once_selected(client):
    res = path_a_sos(client, gps=DINDIGUL)
    case = res.json()["case"]
    helper_id = case["helper_id"]
    cid = case["case_id"]

    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    confirm_hospital(client, cid, helper_id=helper_id)

    ambulances = client.get("/ambulances").json()
    mine = next(a for a in ambulances if a["helper_user_id"] == helper_id)
    assert mine["status"] == "en_route_to_hospital"
