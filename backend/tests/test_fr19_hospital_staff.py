"""FR-19 Doctor/Staff Roster + On-Duty Status."""


def test_create_and_list_staff(client):
    res = client.post(
        "/hospitals/HOSP-001/staff",
        json={"full_name": "Dr. Meera Nair", "staff_category": "doctor", "specialty": "cardiology"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["hospital_id"] == "HOSP-001"
    assert body["on_duty_status"] == "off_duty"
    assert body["is_active"] is True

    listed = client.get("/hospitals/HOSP-001/staff").json()
    assert any(s["staff_id"] == body["staff_id"] for s in listed)


def test_unknown_hospital_404s(client):
    res = client.post("/hospitals/HOSP-999/staff", json={"full_name": "X", "staff_category": "nurse"})
    assert res.status_code == 404


def test_receptionist_scoped_to_own_hospital(client_factory):
    recep1 = client_factory("recep-hosp-001")
    recep4 = client_factory("recep-hosp-004")

    ok = recep1.post("/hospitals/HOSP-001/staff", json={"full_name": "Local Nurse", "staff_category": "nurse"})
    assert ok.status_code == 200

    forbidden = recep4.post("/hospitals/HOSP-001/staff", json={"full_name": "X", "staff_category": "nurse"})
    assert forbidden.status_code == 403
    assert recep4.get("/hospitals/HOSP-001/staff").status_code == 403


def test_on_duty_toggle(client):
    s = client.post("/hospitals/HOSP-001/staff", json={"full_name": "X", "staff_category": "doctor"}).json()
    res = client.patch(f"/staff/{s['staff_id']}/on-duty-status", json={"on_duty_status": "on_duty"})
    assert res.status_code == 200
    assert res.json()["on_duty_status"] == "on_duty"

    res2 = client.patch(f"/staff/{s['staff_id']}/on-duty-status", json={"on_duty_status": "on_leave"})
    assert res2.status_code == 200
    assert res2.json()["on_duty_status"] == "on_leave"


def test_unknown_staff_404s(client):
    assert client.patch("/staff/does-not-exist/on-duty-status", json={"on_duty_status": "on_duty"}).status_code == 404
    assert client.delete("/staff/does-not-exist").status_code == 404


def test_soft_delete_keeps_history_queryable(client):
    s = client.post("/hospitals/HOSP-001/staff", json={"full_name": "X", "staff_category": "technician"}).json()
    client.patch(f"/staff/{s['staff_id']}/on-duty-status", json={"on_duty_status": "on_duty"})

    res = client.delete(f"/staff/{s['staff_id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["is_active"] is False
    assert body["on_duty_status"] == "off_duty"  # soft-delete also clears on-duty

    # excluded from the default (active-only) list...
    active = client.get("/hospitals/HOSP-001/staff").json()
    assert not any(x["staff_id"] == s["staff_id"] for x in active)

    # ...but still queryable via include_inactive, preserving history
    everyone = client.get("/hospitals/HOSP-001/staff?include_inactive=true").json()
    assert any(x["staff_id"] == s["staff_id"] for x in everyone)


def test_admin_only_unscoped_staff_list(client, client_factory):
    client.post("/hospitals/HOSP-001/staff", json={"full_name": "A", "staff_category": "doctor"})
    client.post("/hospitals/HOSP-004/staff", json={"full_name": "B", "staff_category": "nurse"})

    res = client.get("/staff")
    assert res.status_code == 200
    hospital_ids = {s["hospital_id"] for s in res.json()}
    assert {"HOSP-001", "HOSP-004"}.issubset(hospital_ids)

    recep = client_factory("recep-hosp-001")
    assert recep.get("/staff").status_code == 403
