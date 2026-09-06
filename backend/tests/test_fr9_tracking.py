"""FR-9 Family SMS Tracking Link — Path B only, read-only, token-scoped, expiry."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.case import Case
from app.models.sms import SmsMessage
from app.models.tracking import CaseTrackingToken
from tests.helpers import confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}
DELHI = {"latitude": 28.61, "longitude": 77.20}

# fields the tracking view is allowed to expose — nothing else
ALLOWED_TOP_LEVEL = {"status", "stage", "hospital", "eta", "bed_lock_status", "prep_status", "qr_handoff_status"}


def _path_b_case(client) -> str:
    return client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"name": "Asha", "approx_age": 60, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]


def _path_a_case(client) -> str:
    from tests.helpers import path_a_sos, confirm_hospital
    return path_a_sos(client, gps=DELHI).json()["case"]["case_id"]


def _progress_to_selected(client, cid):
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    confirm_hospital(client, cid)


# ------------------------------------------------------- token creation -------
def test_path_a_case_never_gets_a_tracking_token(client, db_session):
    cid = _path_a_case(client)
    assert db_session.scalar(select(CaseTrackingToken).where(CaseTrackingToken.case_id == cid)) is None


def test_path_b_case_gets_a_token_and_sms_immediately(client, db_session):
    cid = _path_b_case(client)

    row = db_session.scalar(select(CaseTrackingToken).where(CaseTrackingToken.case_id == cid))
    assert row is not None
    assert row.token != cid                       # NOT the sequential case_id
    assert len(row.token) >= 32
    # placeholder far-future expiry at creation
    assert row.token_expires_at > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=365)

    sms = db_session.scalar(select(SmsMessage).where(SmsMessage.case_id == cid, SmsMessage.category == "tracking_link"))
    assert sms is not None
    assert sms.to_phone == "9123456780"
    assert row.token in sms.message
    assert "/track/" in sms.message


# --------------------------------------------------- console tracking-link ---
def test_case_tracking_link_endpoint_gives_helper_the_real_token(client, db_session):
    """The SMS send is a stub — this is how a helper/admin actually gets the
    link to hand the family, and it must be the SAME token /track/ scopes on."""
    cid = _path_b_case(client)
    real_token = db_session.scalar(select(CaseTrackingToken.token).where(CaseTrackingToken.case_id == cid))

    res = client.get(f"/cases/{cid}/tracking-link")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["token"] == real_token
    assert body["expires_at"]

    # and that token really works against the public endpoint
    assert client.get(f"/track/{body['token']}").status_code == 200


def test_path_a_case_has_no_tracking_link(client):
    cid = _path_a_case(client)
    assert client.get(f"/cases/{cid}/tracking-link").status_code == 404


def test_tracking_link_endpoint_respects_case_access_scoping(client_factory):
    helper = client_factory("HLP-001")
    cid = helper.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 40, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]

    other_helper = client_factory("HLP-002")
    assert other_helper.get(f"/cases/{cid}/tracking-link").status_code == 403

    unauthenticated = client_factory(None)
    assert unauthenticated.get(f"/cases/{cid}/tracking-link").status_code == 401


# ------------------------------------------------------- read-only view -------
def test_track_endpoint_returns_scoped_live_status(client, db_session):
    cid = _path_b_case(client)
    _progress_to_selected(client, cid)
    # confirm one prep action so prep_status shows progress
    prep = client.get(f"/cases/{cid}/prep-actions").json()["pending"][0]
    client.post(f"/prep-actions/{prep['prep_action_id']}/confirm", json={"receptionist_id": "R"})

    token = db_session.scalar(select(CaseTrackingToken.token).where(CaseTrackingToken.case_id == cid))
    res = client.get(f"/track/{token}")
    assert res.status_code == 200, res.text
    body = res.json()

    assert set(body) == ALLOWED_TOP_LEVEL          # exactly the whitelist, nothing more
    assert body["stage"] == "en_route"
    assert body["hospital"]["name"]
    assert body["hospital"]["cost_tier"]
    assert "rated" in body["hospital"]["why_chosen"]
    assert body["eta"]["min_minutes"] <= body["eta"]["max_minutes"]
    assert body["bed_lock_status"] == "confirmed"
    assert body["prep_status"]["confirmed"] == 1
    assert body["qr_handoff_status"] == "not_yet"

    # no leakage of internal identifiers / patient data anywhere in the payload
    blob = res.text
    assert cid not in blob
    assert "Asha" not in blob
    assert "9123456780" not in blob
    assert "chest_pain" not in blob


def test_track_reflects_qr_handoff_and_discharge(client, db_session):
    cid = _path_b_case(client)
    _progress_to_selected(client, cid)
    tok = client.post(f"/cases/{cid}/qr-handoff").json()["token"]
    client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "NURSE"})

    token = db_session.scalar(select(CaseTrackingToken.token).where(CaseTrackingToken.case_id == cid))
    body = client.get(f"/track/{token}").json()
    assert body["stage"] == "arrived"
    assert body["qr_handoff_status"] == "confirmed"

    client.post(f"/cases/{cid}/trigger-discharge")
    body = client.get(f"/track/{token}").json()
    assert body["stage"] == "discharged"


def test_track_endpoint_is_read_only(client, db_session):
    cid = _path_b_case(client)
    token = db_session.scalar(select(CaseTrackingToken.token).where(CaseTrackingToken.case_id == cid))
    assert client.post(f"/track/{token}", json={}).status_code == 405
    assert client.put(f"/track/{token}", json={}).status_code == 405
    assert client.patch(f"/track/{token}", json={}).status_code == 405
    assert client.delete(f"/track/{token}").status_code == 405


# --------------------------------------------------------- bad / expired -----
def test_invalid_token_returns_clean_not_found(client):
    res = client.get("/track/totally-made-up-token-value-1234567890")
    assert res.status_code == 404
    assert "token" not in res.text.lower() or "not found" in res.text.lower()
    # no case data, no hint about other tokens
    assert "hospital" not in res.json()


def test_expired_token_returns_expired_message_and_no_case_data(client, db_session):
    cid = _path_b_case(client)
    _progress_to_selected(client, cid)
    row = db_session.scalar(select(CaseTrackingToken).where(CaseTrackingToken.case_id == cid))
    row.token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    db_session.commit()

    res = client.get(f"/track/{row.token}")
    assert res.status_code == 410
    body = res.json()
    assert body == {"status": "expired", "message": "This link has expired"}
    assert "hospital" not in res.text and "eta" not in res.text


# --------------------------------------------------------- closure expiry ----
def test_discharge_recomputes_expiry_to_24_48h_after_close(client, db_session):
    cid = _path_b_case(client)
    _progress_to_selected(client, cid)
    tok = client.post(f"/cases/{cid}/qr-handoff").json()["token"]
    client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "N"})
    client.post(f"/cases/{cid}/trigger-discharge")

    db_session.expire_all()
    case = db_session.get(Case, cid)
    row = db_session.scalar(select(CaseTrackingToken).where(CaseTrackingToken.case_id == cid))
    delta_hours = (row.token_expires_at - case.discharged_at).total_seconds() / 3600
    assert 24 <= delta_hours <= 48
