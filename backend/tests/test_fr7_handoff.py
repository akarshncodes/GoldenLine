"""FR-7 QR Handoff at Arrival — token gen, scan, expiry/reuse, admission status."""
import json

from tests.helpers import confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}


def _prepped_case(client, symptoms=("chest_pain",), *, path="B") -> str:
    if path == "B":
        cid = client.post(
            "/cases",
            json={
                "next_of_kin_phone_number": "9123456780",
                "patient": {"name": "Asha Rao", "approx_age": 58, "gender": "female"},
                "helper_id": "HLP-001",
                "helper_gps": BENGALURU,
            },
        ).json()["case_id"]
    else:
        from tests.helpers import path_a_sos
        cid = path_a_sos(client, gps={"latitude": 28.61, "longitude": 77.20}).json()["case"]["case_id"]

    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": list(symptoms), "confirm": True},
    )
    client.patch(
        f"/cases/{cid}/clinical-info",
        json={"known_allergies": "penicillin", "current_medications": "aspirin 75mg", "blood_group": "O+"},
    )
    if path == "B":
        confirm_hospital(client, cid)
    else:
        hid = client.get(f"/cases/{cid}/hospital-ranking").json()["ranked"][0]["hospital_id"]
        client.post(f"/cases/{cid}/select-hospital", json={"hospital_id": hid, "helper_id": "HLP-001"})
    return cid


def _gen(client, cid):
    return client.post(f"/cases/{cid}/qr-handoff").json()


# --------------------------------------------------------- token payload ------
def test_qr_payload_contains_only_a_case_ref_and_token(client):
    cid = _prepped_case(client)
    res = client.post(f"/cases/{cid}/qr-handoff")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["case_id"] == cid
    assert body["token"]
    assert body["expires_at"]

    payload = json.loads(body["qr_payload"])
    assert set(payload) == {"case_id", "token"}          # nothing else baked in
    assert "Asha" not in body["qr_payload"]              # no patient data
    assert "penicillin" not in body["qr_payload"]


def test_cannot_generate_before_a_hospital_is_selected(client):
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 40, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    assert client.post(f"/cases/{cid}/qr-handoff").status_code == 409


# --------------------------------------------------------------- scan --------
def test_scan_returns_full_admission_bundle_and_marks_admitted(client):
    cid = _prepped_case(client, symptoms=["chest_pain", "breathing_difficulty"])
    tok = _gen(client, cid)["token"]

    res = client.post(
        "/qr-handoff/scan",
        json={"case_id": cid, "token": tok, "scanned_by": "NURSE-7"},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["status"] == "ADMITTED"
    assert body["logged_symptoms"]["symptom_checklist"] == ["chest_pain", "breathing_difficulty"]

    adm = body["admission_ready_data"]
    assert adm["patient_identity"]["name"] == "Asha Rao"
    assert adm["known_allergies"] == "penicillin"
    assert adm["current_medications"] == "aspirin 75mg"
    assert adm["blood_group"] == "O+"
    assert adm["next_of_kin"] == "9123456780"
    assert adm["scheme_status"] == "not_indicated"

    # transit timeline derived from stored timestamps, in order
    tl = body["transit_timeline"]
    kinds = [e["event"] for e in tl]
    for expected in ("case_created", "symptoms_logged", "hospital_selected", "bed_locked", "qr_handoff_scanned"):
        assert expected in kinds
    # chronological, and the pipeline stages come in the right relative order
    times = [e["at"] for e in tl]
    assert times == sorted(times)
    assert kinds.index("symptoms_logged") < kinds.index("hospital_selected") < kinds.index("qr_handoff_scanned")

    # the case is now admitted
    assert client.get(f"/cases/{cid}").json()["status"] == "ADMITTED"


def test_second_scan_with_same_token_is_rejected_with_no_data(client):
    cid = _prepped_case(client)
    tok = _gen(client, cid)["token"]

    assert client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "N1"}).status_code == 200

    res = client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "N2"})
    assert res.status_code == 403
    detail = res.json()["detail"]
    assert "Asha" not in detail and "penicillin" not in detail  # no leak
    assert "9123456780" not in detail


def test_wrong_case_for_token_is_rejected(client):
    cid1 = _prepped_case(client)
    cid2 = _prepped_case(client)
    tok1 = _gen(client, cid1)["token"]
    assert client.post(
        "/qr-handoff/scan", json={"case_id": cid2, "token": tok1, "scanned_by": "N"}
    ).status_code == 403


def test_unknown_token_is_rejected(client):
    cid = _prepped_case(client)
    assert client.post(
        "/qr-handoff/scan", json={"case_id": cid, "token": "not-a-real-token", "scanned_by": "N"}
    ).status_code == 403


def test_regenerate_invalidates_the_previous_token_expiry_path(client, db_session):
    """Regenerating expires the old token (expires_at set to now) — the same code
    path an actually-expired token hits. And a hand-expired token also returns 403."""
    cid = _prepped_case(client)
    old = _gen(client, cid)["token"]
    new = _gen(client, cid)["token"]
    assert old != new
    assert client.post("/qr-handoff/scan", json={"case_id": cid, "token": old, "scanned_by": "N"}).status_code == 403
    assert client.post("/qr-handoff/scan", json={"case_id": cid, "token": new, "scanned_by": "N"}).status_code == 200

    # hand-expire the fresh token and confirm no data comes back
    from datetime import datetime, timedelta, timezone

    from app.models.handoff import QrHandoffToken

    row = db_session.query(QrHandoffToken).filter(QrHandoffToken.token == new).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    res = client.post("/qr-handoff/scan", json={"case_id": cid, "token": new, "scanned_by": "N"})
    assert res.status_code == 403
    assert "Asha" not in res.json()["detail"]


def test_no_freeform_fields_accepted_on_scan(client):
    cid = _prepped_case(client)
    tok = _gen(client, cid)["token"]
    assert client.post(
        "/qr-handoff/scan",
        json={"case_id": cid, "token": tok, "scanned_by": "N", "notes": "anything"},
    ).status_code == 422
