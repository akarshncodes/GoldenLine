"""FR-8 Discharge Feedback — trigger discharge, one structured submission per case."""
from sqlalchemy import func, select

from tests.helpers import confirm_hospital

from app.models.feedback import CaseFeedback

BENGALURU = {"latitude": 12.97, "longitude": 77.59}

GOOD_FEEDBACK = {
    "wait_time_tag": 4,
    "staff_behavior_tag": 5,
    "cleanliness_tag": 3,
    "billing_tag": 4,
    "ready_as_shown_tag": "yes",
}


def _admitted_case(client) -> str:
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"name": "Ravi", "approx_age": 60, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    confirm_hospital(client, cid)
    tok = client.post(f"/cases/{cid}/qr-handoff").json()["token"]
    client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "NURSE-1"})
    return cid


# --------------------------------------------------------- trigger discharge --
def test_trigger_discharge_marks_case_and_sends_feedback_link(client):
    cid = _admitted_case(client)
    res = client.post(f"/cases/{cid}/trigger-discharge")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["case_id"] == cid
    assert body["link"].startswith("https://")
    assert body["recipient_phone"] == "9123456780"
    assert body["sms_sent_at"] is not None

    assert client.get(f"/cases/{cid}").json()["status"] == "DISCHARGED"


def test_cannot_discharge_a_case_that_was_never_admitted(client):
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 40, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    assert client.post(f"/cases/{cid}/trigger-discharge").status_code == 409


def test_double_discharge_is_rejected(client):
    cid = _admitted_case(client)
    assert client.post(f"/cases/{cid}/trigger-discharge").status_code == 201
    assert client.post(f"/cases/{cid}/trigger-discharge").status_code == 409


# --------------------------------------------------------------- feedback -----
def test_feedback_before_discharge_is_rejected(client):
    cid = _admitted_case(client)
    res = client.post(f"/cases/{cid}/feedback", json={"token": "x", **GOOD_FEEDBACK})
    assert res.status_code == 409


def test_feedback_submits_once_then_db_constraint_rejects_the_second(client, db_session):
    cid = _admitted_case(client)
    invite = client.post(f"/cases/{cid}/trigger-discharge").json()
    tok = invite["link"].rsplit("/", 1)[-1]

    first = client.post(f"/cases/{cid}/feedback", json={"token": tok, **GOOD_FEEDBACK})
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["wait_time_tag"] == 4
    assert body["ready_as_shown_tag"] == "yes"
    assert body["hospital_id"] is not None  # denormalised for the future reliability score

    second = client.post(
        f"/cases/{cid}/feedback",
        json={"token": tok, "wait_time_tag": 1, "staff_behavior_tag": 1,
              "cleanliness_tag": 1, "billing_tag": 1, "ready_as_shown_tag": "no"},
    )
    assert second.status_code == 409
    assert "constraint" in second.json()["detail"].lower()

    # exactly one row, and it's the ORIGINAL (not overwritten)
    count = db_session.scalar(select(func.count()).select_from(CaseFeedback).where(CaseFeedback.case_id == cid))
    assert count == 1
    stored = db_session.scalar(select(CaseFeedback).where(CaseFeedback.case_id == cid))
    assert stored.wait_time_tag == 4  # unchanged


def test_feedback_table_has_a_real_unique_constraint_on_case_id(client, db_session):
    from sqlalchemy import inspect

    uniques = inspect(db_session.get_bind()).get_unique_constraints("case_feedback")
    assert any(u["column_names"] == ["case_id"] for u in uniques), uniques


def test_no_freeform_text_field_accepted(client):
    cid = _admitted_case(client)
    tok = client.post(f"/cases/{cid}/trigger-discharge").json()["link"].rsplit("/", 1)[-1]
    res = client.post(
        f"/cases/{cid}/feedback",
        json={"token": tok, **GOOD_FEEDBACK, "comments": "the staff were rude"},
    )
    assert res.status_code == 422  # extra="forbid" blocks it


def test_star_tags_out_of_range_rejected(client):
    cid = _admitted_case(client)
    tok = client.post(f"/cases/{cid}/trigger-discharge").json()["link"].rsplit("/", 1)[-1]
    res = client.post(
        f"/cases/{cid}/feedback",
        json={"token": tok, **{**GOOD_FEEDBACK, "wait_time_tag": 9}},
    )
    assert res.status_code == 422


def test_invalid_ready_as_shown_tag_rejected(client):
    cid = _admitted_case(client)
    tok = client.post(f"/cases/{cid}/trigger-discharge").json()["link"].rsplit("/", 1)[-1]
    res = client.post(
        f"/cases/{cid}/feedback",
        json={"token": tok, **{**GOOD_FEEDBACK, "ready_as_shown_tag": "maybe"}},
    )
    assert res.status_code == 422
