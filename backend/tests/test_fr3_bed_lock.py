"""FR-3 Bed Lock — auto-lock on selection, availability, release, conflict log."""

from tests.helpers import path_a_sos, confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}
DELHI = {"latitude": 28.61, "longitude": 77.20}


def _path_b_case(client, symptoms=("chest_pain",), criticality="Serious") -> str:
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 60, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    r = client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": criticality, "symptom_checklist": list(symptoms), "confirm": True},
    )
    assert r.status_code == 201, r.text
    return cid


def _path_a_case(client, symptoms=("chest_pain",), gps=None) -> str:
    cid = path_a_sos(client, gps=gps or DELHI).json()["case"]["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": list(symptoms), "confirm": True},
    )
    return cid


def _dash(client, hospital_id):
    rows = client.get("/hospitals/dashboard").json()
    return next(r for r in rows if r["hospital_id"] == hospital_id)


# ------------------------------------------------- auto-lock on selection -------
def test_confirm_hospital_places_a_bed_lock(client):
    cid = _path_b_case(client)
    res = confirm_hospital(client, cid)
    assert res.status_code == 201, res.text
    body = res.json()
    hid = body["selected_hospital_id"]

    assert body["bed_lock"]["hospital_id"] == hid
    assert body["bed_lock"]["case_id"] == cid
    assert body["bed_lock"]["bed_type"] == "general"     # Serious -> general
    assert body["bed_lock"]["lock_status"] == "active"

    got = client.get(f"/cases/{cid}/bed-lock").json()
    assert got["bed_lock_id"] == body["bed_lock"]["bed_lock_id"]


def test_critical_case_locks_an_icu_slot(client):
    cid = _path_b_case(client, symptoms=["chest_pain"], criticality="Critical")
    body = confirm_hospital(client, cid).json()
    assert body["bed_lock"]["bed_type"] == "ICU"


def test_lock_reduces_available_count_and_release_restores_it(client):
    cid = _path_b_case(client)
    # find which hospital will be picked (rank #1)
    hid = client.get(f"/cases/{cid}/hospital-ranking").json()["ranked"][0]["hospital_id"]
    before = _dash(client, hid)["available_general_beds"]

    confirm_hospital(client, cid)
    after_lock = _dash(client, hid)["available_general_beds"]
    assert after_lock == before - 1

    rel = client.post(f"/cases/{cid}/bed-lock/release")
    assert rel.status_code == 200, rel.text
    assert rel.json()["released_lock"]["lock_status"] == "released"
    assert rel.json()["case_selection_cleared"] is True

    after_release = _dash(client, hid)["available_general_beds"]
    assert after_release == before


def test_release_clears_selection_so_case_can_be_reassigned(client):
    cid = _path_b_case(client)
    first = confirm_hospital(client, cid).json()["selected_hospital_id"]

    client.post(f"/cases/{cid}/bed-lock/release")
    assert client.get(f"/cases/{cid}").json()["selected_hospital_id"] is None

    again = confirm_hospital(client, cid)
    assert again.status_code == 201
    assert again.json()["selected_hospital_id"] == first  # same hospital free again


def test_release_without_an_active_lock_is_404(client):
    cid = _path_b_case(client)
    assert client.post(f"/cases/{cid}/bed-lock/release").status_code == 404


# ------------------------------------------- capacity exclusion in ranking -----
def test_full_icu_hospital_excluded_then_available_again_after_release(client):
    # HOSP-009 (City Hospital, Private-Standard) has cardiology and is the
    # moderate-tier class pick for chest_pain (see test_fr2_hospital_ranking.py)
    # — exhaust its ICU capacity entirely, one Critical case per bed.
    hid = "HOSP-009"
    icu_capacity = next(h for h in client.get("/hospitals").json() if h["hospital_id"] == hid)["live_icu_count"]
    locked_cases = []
    for i in range(icu_capacity):
        # spread the SOS locations so FR-12 duplicate-merge doesn't fold them
        cid = _path_a_case(client, symptoms=["chest_pain"], gps={"latitude": 28.61 + i, "longitude": 77.20})
        client.post(f"/cases/{cid}/assessment/checklist",
                    json={"criticality_level": "Critical", "symptom_checklist": ["chest_pain"], "confirm": True})
        classes = client.get(f"/cases/{cid}/hospital-ranking").json()["classes"]
        assert classes["moderate"]["hospital_id"] == hid  # still the pick while capacity remains
        res = client.post(
            f"/cases/{cid}/select-hospital",
            json={"hospital_id": hid, "helper_id": "HLP-001"},
        )
        assert res.status_code == 201, res.text
        locked_cases.append(cid)

    assert _dash(client, hid)["available_icu_beds"] == 0

    # a new Critical cardiology case: HOSP-009 is now excluded for no capacity
    newc = _path_a_case(client, symptoms=["chest_pain"], gps={"latitude": 19.07, "longitude": 72.87})
    client.post(f"/cases/{newc}/assessment/checklist",
                json={"criticality_level": "Critical", "symptom_checklist": ["chest_pain"], "confirm": True})
    ranking = client.get(f"/cases/{newc}/hospital-ranking").json()
    assert hid in ranking["excluded_no_capacity_ids"]
    assert hid not in [h["hospital_id"] for h in ranking["ranked"]]
    assert ranking["classes"]["moderate"]["hospital_id"] != hid  # falls through to the next best

    # trying to select it anyway is rejected (not a valid class pick anymore)
    assert client.post(
        f"/cases/{newc}/select-hospital", json={"hospital_id": hid, "helper_id": "HLP-001"}
    ).status_code == 400

    # release one -> it reappears
    client.post(f"/cases/{locked_cases[0]}/bed-lock/release")
    ranking2 = client.get(f"/cases/{newc}/hospital-ranking").json()
    assert hid in [h["hospital_id"] for h in ranking2["ranked"]]


# ------------------------------------------------------- dashboard -------------
def test_dashboard_lists_the_locked_case(client):
    cid = _path_b_case(client)
    hid = confirm_hospital(client, cid).json()["selected_hospital_id"]

    row = _dash(client, hid)
    assert row["active_general_locks"] == 1
    assert [lk["case_id"] for lk in row["locked_for_cases"]] == [cid]
