"""FR-4 — route + ETA range, automatic traffic alert, BLS-vs-ALS waypoint suggestion."""
from tests.helpers import confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}
DELHI = {"latitude": 28.61, "longitude": 77.20}


def _select_path_b(client, symptoms, criticality="Serious", helper_gps=BENGALURU) -> tuple[str, str]:
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 55, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": helper_gps,
        },
    ).json()["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": criticality, "symptom_checklist": list(symptoms), "confirm": True},
    )
    hid = confirm_hospital(client, cid).json()["selected_hospital_id"]
    return cid, hid


# ------------------------------------------------------------- route + ETA -----
def test_route_created_on_selection_with_eta_range(client):
    cid, hid = _select_path_b(client, ["chest_pain"])
    res = client.get(f"/cases/{cid}/route")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["hospital_id"] == hid
    assert body["route_source"] == "stub"          # no GOOGLE_MAPS_API_KEY in tests
    assert body["route_polyline"]
    # Map view: even the straight-line stub gives the client two drawable points,
    # starting at the helper's reported location.
    assert len(body["route_path"]) == 2
    assert body["route_path"][0] == [BENGALURU["latitude"], BENGALURU["longitude"]]
    # ETA is always a range, not a single number
    assert body["eta_min_minutes"] <= body["eta_minutes"] <= body["eta_max_minutes"]
    assert body["eta_max_minutes"] > body["eta_min_minutes"]


def test_route_uses_external_api_seam_not_a_custom_calculation(client):
    """The stub is clearly labelled; a real key routes through app.services.maps.get_route."""
    import inspect

    from app.services import maps

    src = inspect.getsource(maps)
    assert "maps.googleapis.com" in src          # genuine external endpoint
    assert "httpx" in src                        # real HTTP client
    assert 'source="stub"' in src or "source='stub'" in src


# --------------------------------------------------------- traffic alert -------
def test_traffic_alert_created_for_every_case_path_a_and_b(client):
    # Path B
    cid_b, _ = _select_path_b(client, ["high_fever"])
    alert_b = client.get(f"/cases/{cid_b}/traffic-alert").json()
    assert "Local Traffic Control" in alert_b["traffic_alert_recipients"]
    assert alert_b["traffic_alert_sent_at"] is not None

    # Path A
    from tests.helpers import path_a_sos, confirm_hospital
    cid_a = path_a_sos(client, gps=DELHI).json()["case"]["case_id"]
    client.post(
        f"/cases/{cid_a}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    ranked = client.get(f"/cases/{cid_a}/hospital-ranking").json()["ranked"]
    client.post(
        f"/cases/{cid_a}/select-hospital",
        json={"hospital_id": ranked[0]["hospital_id"], "helper_id": "HLP-001"},
    )
    assert client.get(f"/cases/{cid_a}/traffic-alert").status_code == 200


# -------------------------------------------------- waypoint suggestion --------
def test_als_risk_on_bls_ambulance_triggers_waypoint_suggestion(client):
    cid, _ = _select_path_b(client, ["chest_pain", "breathing_difficulty"], criticality="Critical")
    res = client.get(f"/cases/{cid}/waypoint-suggestion")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "suggested"
    assert body["waypoint_id"].startswith("WP-")
    assert "ALS" in body["reason"]


def test_waypoint_suggestion_requires_explicit_helper_accept(client):
    cid, _ = _select_path_b(client, ["chest_pain", "breathing_difficulty"], criticality="Critical")
    # nothing is applied automatically
    assert client.get(f"/cases/{cid}/waypoint-suggestion").json()["status"] == "suggested"

    res = client.post(
        f"/cases/{cid}/waypoint-suggestion/accept", json={"helper_id": "HLP-001"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "accepted"
    assert res.json()["decided_by"] == "HLP-001"

    # a second decision is rejected
    assert client.post(
        f"/cases/{cid}/waypoint-suggestion/decline", json={"helper_id": "HLP-001"}
    ).status_code == 404


def test_no_waypoint_when_not_als_risk(client):
    cid, _ = _select_path_b(client, ["high_fever"])
    assert client.get(f"/cases/{cid}/waypoint-suggestion").status_code == 404


def test_no_waypoint_when_ambulance_is_als(client):
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 55, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Critical", "symptom_checklist": ["chest_pain", "breathing_difficulty"], "confirm": True},
    )
    client.put(f"/cases/{cid}/ambulance-level", json={"ambulance_level": "ALS"})
    confirm_hospital(client, cid)

    assert client.get(f"/cases/{cid}/waypoint-suggestion").status_code == 404
