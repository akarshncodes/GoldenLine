"""FR-5 — conditional blood check + blood-bank hold + coordinator decision."""
from tests.helpers import confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}


def _select_path_a(client, symptoms, hospital_id=None):
    from tests.helpers import path_a_sos, confirm_hospital
    cid = path_a_sos(client, gps={"latitude": 12.97, "longitude": 77.59}).json()["case"]["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": list(symptoms), "confirm": True},
    )
    ranked = client.get(f"/cases/{cid}/hospital-ranking").json()["ranked"]
    target = hospital_id or ranked[0]["hospital_id"]
    client.post(
        f"/cases/{cid}/select-hospital",
        json={"hospital_id": target, "helper_id": "HLP-001"},
    )
    return cid, target


def _select_path_b(client, symptoms):
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 40, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": list(symptoms), "confirm": True},
    )
    hid = confirm_hospital(client, cid).json()["selected_hospital_id"]
    return cid, hid


# ------------------------------------------------------- conditional trigger ---
def test_blood_check_not_run_without_bleeding_or_trauma(client):
    cid, _ = _select_path_b(client, ["chest_pain"])
    assert client.get(f"/cases/{cid}/blood-check").status_code == 404
    assert client.get(f"/cases/{cid}/blood-bank-hold").status_code == 404


def test_visible_bleeding_triggers_a_blood_check(client):
    cid, hid = _select_path_b(client, ["visible_bleeding"])   # needs trauma_surgery -> HOSP-001 (O-: 1)
    res = client.get(f"/cases/{cid}/blood-check")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["blood_requirement_flag"] is True
    assert body["triggered_by_symptoms"] == ["visible_bleeding"]
    assert body["hospital_id"] == hid


def test_insufficient_hospital_stock_creates_a_blood_bank_hold(client):
    # HOSP-001 ranks #1 for a bleeding case and has O-: 1 (< 2 units needed) -> hold
    cid, hid = _select_path_b(client, ["visible_bleeding", "trauma"])
    assert hid == "HOSP-001"
    check = client.get(f"/cases/{cid}/blood-check").json()
    assert check["hospital_stock_sufficient"] is False
    assert check["outcome"] == "blood_bank_hold_requested"

    hold = client.get(f"/cases/{cid}/blood-bank-hold").json()
    assert hold["hold_status"] == "pending"
    assert hold["units_requested"] == 2
    assert hold["blood_bank_id"] == "BB-01"          # BB-01 is linked to HOSP-001

    # it shows on the blood bank coordinator's dashboard
    dash = client.get("/blood-banks/BB-01/holds").json()
    assert any(h["blood_bank_hold_id"] == hold["blood_bank_hold_id"] for h in dash)


def test_admin_sees_all_holds_across_every_bank(client):
    """Admin has no blood_bank_id of its own — the unscoped view is how it
    sees hold requests at all (was previously always empty, a real bug)."""
    cid, hid = _select_path_b(client, ["visible_bleeding", "trauma"])
    hold = client.get(f"/cases/{cid}/blood-bank-hold").json()

    res = client.get("/blood-bank-holds")
    assert res.status_code == 200, res.text
    all_holds = res.json()
    assert any(h["blood_bank_hold_id"] == hold["blood_bank_hold_id"] for h in all_holds)
    assert any(h["blood_bank_id"] == "BB-01" for h in all_holds)


def test_all_holds_endpoint_requires_admin_or_control_room(client_factory):
    coordinator = client_factory("coord-bb-01")
    assert coordinator.get("/blood-bank-holds").status_code == 403

    helper = client_factory("HLP-001")
    assert helper.get("/blood-bank-holds").status_code == 403

    control_room = client_factory("control-room")
    assert control_room.get("/blood-bank-holds").status_code == 200


def test_sufficient_hospital_stock_places_no_hold(client):
    # moderate class-pick for trauma_surgery is HOSP-005 (Lakeside), O-: 5 -> sufficient
    cid, hid = _select_path_a(client, ["visible_bleeding"], hospital_id="HOSP-005")
    assert hid == "HOSP-005"
    check = client.get(f"/cases/{cid}/blood-check").json()
    assert check["hospital_stock_sufficient"] is True
    assert check["outcome"] == "hospital_stock_ok"
    assert client.get(f"/cases/{cid}/blood-bank-hold").status_code == 404


def test_coordinator_can_confirm_and_then_not_re_decide(client):
    cid, _ = _select_path_b(client, ["visible_bleeding", "trauma"])
    hold_id = client.get(f"/cases/{cid}/blood-bank-hold").json()["blood_bank_hold_id"]

    res = client.post(f"/blood-bank-holds/{hold_id}/confirm", json={"coordinator_id": "COORD-1"})
    assert res.status_code == 200
    assert res.json()["hold_status"] == "confirmed"
    assert res.json()["decided_by"] == "COORD-1"

    again = client.post(f"/blood-bank-holds/{hold_id}/reject", json={"coordinator_id": "COORD-1"})
    assert again.status_code == 409


def test_coordinator_can_reject(client):
    cid, _ = _select_path_b(client, ["visible_bleeding", "trauma"])
    hold_id = client.get(f"/cases/{cid}/blood-bank-hold").json()["blood_bank_hold_id"]
    res = client.post(f"/blood-bank-holds/{hold_id}/reject", json={"coordinator_id": "COORD-2"})
    assert res.status_code == 200
    assert res.json()["hold_status"] == "rejected"


def test_blood_banks_seeded(client):
    banks = client.get("/blood-banks").json()
    assert len(banks) == 3
    assert {b["blood_bank_id"] for b in banks} == {"BB-01", "BB-02", "BB-03"}


def test_case_with_neither_symptom_skips_both_fr4_waypoint_and_fr5_blood(client):
    cid, _ = _select_path_b(client, ["high_fever"])   # neither ALS-risk nor bleeding/trauma
    assert client.get(f"/cases/{cid}/route").status_code == 200          # route always
    assert client.get(f"/cases/{cid}/traffic-alert").status_code == 200  # traffic alert always
    assert client.get(f"/cases/{cid}/waypoint-suggestion").status_code == 404  # no waypoint
    assert client.get(f"/cases/{cid}/blood-check").status_code == 404          # no blood check
