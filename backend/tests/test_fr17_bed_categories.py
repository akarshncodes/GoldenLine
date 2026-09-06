"""FR-17 Bed/Room Categories.

Additive: capacity beyond general+ICU, hospital-scoped, never touches
live_bed_count/live_icu_count.
"""


def test_new_hospital_has_no_categories_yet(client):
    res = client.get("/hospitals/HOSP-001/bed-categories")
    assert res.status_code == 200
    assert res.json() == []


def test_admin_can_create_and_update_a_category(client):
    res = client.put(
        "/hospitals/HOSP-001/bed-categories/private",
        json={"label": "Private Room", "total_beds": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["category_code"] == "private"
    assert body["label"] == "Private Room"
    assert body["total_beds"] == 5

    # upsert: same code updates in place, doesn't duplicate
    res2 = client.put(
        "/hospitals/HOSP-001/bed-categories/private",
        json={"label": "Private Room", "total_beds": 8},
    )
    assert res2.status_code == 200
    assert res2.json()["total_beds"] == 8

    listed = client.get("/hospitals/HOSP-001/bed-categories").json()
    assert len(listed) == 1
    assert listed[0]["total_beds"] == 8


def test_upsert_unknown_hospital_404s(client):
    res = client.put(
        "/hospitals/HOSP-999/bed-categories/private",
        json={"label": "Private Room", "total_beds": 5},
    )
    assert res.status_code == 404


def test_snapshot_merges_general_icu_with_categories(client):
    client.put("/hospitals/HOSP-001/bed-categories/ward", json={"label": "General Ward", "total_beds": 20})
    hospital = client.get("/hospitals").json()
    h1 = next(h for h in hospital if h["hospital_id"] == "HOSP-001")

    res = client.get("/hospitals/HOSP-001/bed-categories/snapshot")
    assert res.status_code == 200
    body = res.json()
    assert body["general_total"] == h1["live_bed_count"]
    assert body["icu_total"] == h1["live_icu_count"]
    assert len(body["categories"]) == 1
    assert body["categories"][0]["category_code"] == "ward"


def test_receptionist_can_manage_only_their_own_hospital(client_factory):
    recep1 = client_factory("recep-hosp-001")  # HOSP-001
    recep4 = client_factory("recep-hosp-004")  # HOSP-004

    ok = recep1.put("/hospitals/HOSP-001/bed-categories/isolation", json={"label": "Isolation", "total_beds": 2})
    assert ok.status_code == 200

    forbidden = recep4.put(
        "/hospitals/HOSP-001/bed-categories/isolation", json={"label": "Isolation", "total_beds": 2}
    )
    assert forbidden.status_code == 403

    forbidden_read = recep4.get("/hospitals/HOSP-001/bed-categories")
    assert forbidden_read.status_code == 403


def test_family_role_forbidden(client_factory):
    family = client_factory("HLP-001")  # not a receptionist/admin/control_room
    res = family.get("/hospitals/HOSP-001/bed-categories")
    assert res.status_code == 403


def test_admin_only_unscoped_list(client, client_factory):
    client.put("/hospitals/HOSP-001/bed-categories/ward", json={"label": "Ward", "total_beds": 10})
    client.put("/hospitals/HOSP-004/bed-categories/ward", json={"label": "Ward", "total_beds": 6})

    res = client.get("/bed-categories")
    assert res.status_code == 200
    codes = {(row["hospital_id"], row["category_code"]) for row in res.json()}
    assert ("HOSP-001", "ward") in codes
    assert ("HOSP-004", "ward") in codes

    recep = client_factory("recep-hosp-001")
    assert recep.get("/bed-categories").status_code == 403
