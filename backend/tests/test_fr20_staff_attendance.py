"""FR-20 Staff Attendance / Clock-in-out."""


def _staff(client, hospital_id="HOSP-001", category="doctor") -> str:
    return client.post(
        f"/hospitals/{hospital_id}/staff", json={"full_name": "X", "staff_category": category}
    ).json()["staff_id"]


def test_clock_in_and_out_lifecycle(client):
    staff_id = _staff(client)

    in_res = client.post(f"/staff/{staff_id}/clock-in", json={"shift_label": "morning"})
    assert in_res.status_code == 200, in_res.text
    body = in_res.json()
    assert body["staff_id"] == staff_id
    assert body["clock_out_at"] is None
    assert body["shift_label"] == "morning"

    out_res = client.post(f"/staff/{staff_id}/clock-out")
    assert out_res.status_code == 200
    assert out_res.json()["clock_out_at"] is not None
    assert out_res.json()["attendance_id"] == body["attendance_id"]


def test_clock_in_sets_on_duty_and_clock_out_clears_it(client):
    staff_id = _staff(client)
    assert client.get("/hospitals/HOSP-001/staff").json()[0]["on_duty_status"] == "off_duty"

    client.post(f"/staff/{staff_id}/clock-in", json={})
    roster = client.get("/hospitals/HOSP-001/staff").json()
    assert next(s for s in roster if s["staff_id"] == staff_id)["on_duty_status"] == "on_duty"

    client.post(f"/staff/{staff_id}/clock-out")
    roster2 = client.get("/hospitals/HOSP-001/staff").json()
    assert next(s for s in roster2 if s["staff_id"] == staff_id)["on_duty_status"] == "off_duty"


def test_double_clock_in_rejected(client):
    staff_id = _staff(client)
    client.post(f"/staff/{staff_id}/clock-in", json={})
    again = client.post(f"/staff/{staff_id}/clock-in", json={})
    assert again.status_code == 409


def test_clock_out_without_clock_in_rejected(client):
    staff_id = _staff(client)
    res = client.post(f"/staff/{staff_id}/clock-out")
    assert res.status_code == 409


def test_unknown_staff_404s(client):
    assert client.post("/staff/does-not-exist/clock-in", json={}).status_code == 404
    assert client.post("/staff/does-not-exist/clock-out").status_code == 404
    assert client.get("/staff/does-not-exist/attendance").status_code == 404


def test_history_ordering_and_scoping(client, client_factory):
    staff_id = _staff(client)
    client.post(f"/staff/{staff_id}/clock-in", json={"shift_label": "morning"})
    client.post(f"/staff/{staff_id}/clock-out")
    client.post(f"/staff/{staff_id}/clock-in", json={"shift_label": "evening"})

    history = client.get(f"/staff/{staff_id}/attendance").json()
    assert len(history) == 2
    assert history[0]["shift_label"] == "evening"  # newest first

    hosp_history = client.get("/hospitals/HOSP-001/attendance").json()
    assert len(hosp_history) == 2

    recep4 = client_factory("recep-hosp-004")
    assert recep4.get(f"/staff/{staff_id}/attendance").status_code == 403
    assert recep4.get("/hospitals/HOSP-001/attendance").status_code == 403
