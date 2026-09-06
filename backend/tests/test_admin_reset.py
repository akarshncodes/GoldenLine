"""Admin-only demo reset — not a formal FRP requirement, added for judge demos."""
from tests.helpers import confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}


def _messy_case(client) -> str:
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"name": "Asha", "approx_age": 60, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    hid = confirm_hospital(client, cid).json()["selected_hospital_id"]
    return cid, hid


def test_reset_clears_cases_and_restores_hospital_counters(client):
    from app.services.hospital_seed import SEED_HOSPITALS

    cid, hid = _messy_case(client)
    seed = next(h for h in SEED_HOSPITALS if h["hospital_id"] == hid)

    dash_before = next(r for r in client.get("/hospitals/dashboard").json() if r["hospital_id"] == hid)
    assert dash_before["available_general_beds"] == seed["live_bed_count"] - 1

    res = client.post("/admin/reset-demo-data")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reset"] is True
    assert body["hospitals_reset"] == len(SEED_HOSPITALS)

    assert client.get(f"/cases/{cid}").status_code == 404
    assert client.get("/cases").json() == []

    dash_after = next(r for r in client.get("/hospitals/dashboard").json() if r["hospital_id"] == hid)
    assert dash_after["available_general_beds"] == seed["live_bed_count"]
    assert dash_after["total_general_beds"] == seed["live_bed_count"]
    assert dash_after["total_icu_beds"] == seed["live_icu_count"]


def test_reset_restores_blood_bank_stock(client):
    from app.services.reference_seed import SEED_BLOOD_BANKS

    cid, hid = _messy_case(client)
    # force a blood-check + hold to mutate demo state around this hospital
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain", "visible_bleeding"], "confirm": True},
    )

    client.post("/admin/reset-demo-data")

    bank = SEED_BLOOD_BANKS[0]
    got = client.get(f"/blood-banks/{bank['blood_bank_id']}/holds")
    assert got.status_code == 200
    assert got.json() == []


def test_reset_is_admin_only(client_factory):
    recep = client_factory("recep-hosp-001")
    assert recep.post("/admin/reset-demo-data").status_code == 403

    helper = client_factory("HLP-001")
    assert helper.post("/admin/reset-demo-data").status_code == 403

    admin = client_factory("admin")
    assert admin.post("/admin/reset-demo-data").status_code == 200


def test_reset_is_idempotent_on_an_already_clean_db(client):
    res1 = client.post("/admin/reset-demo-data")
    res2 = client.post("/admin/reset-demo-data")
    assert res1.status_code == 200
    assert res2.status_code == 200
