"""FR-1 refinement (2026-09-05): matched-keyword transparency + follow-up case notes.

Two related additions, both purely additive/presentational — neither ever
writes back to the assessment's own criticality_level/symptom_checklist:
1. /assessment/voice now also returns which (symptom, keyword) pairs matched,
   so the helper can see *why* something was derived.
2. A new append-only /cases/{id}/notes channel lets a helper log updates
   during a case, separate from the one-time initial-assessment transcript.
"""
from tests.helpers import confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}


def _create_case(client, helper_id="HLP-001") -> str:
    res = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"name": "Asha", "approx_age": 60, "gender": "male"},
            "helper_id": helper_id,
            "helper_gps": BENGALURU,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["case_id"]


# --------------------------------------------------- matched-keyword transparency
def test_voice_derivation_returns_matched_keywords(client):
    case_id = _create_case(client)
    res = client.post(
        f"/cases/{case_id}/assessment/voice",
        json={"transcript": "severe chest pain and breathing difficulty", "language_code": "en"},
    )
    assert res.status_code == 200, res.text
    matches = res.json()["matched_keywords"]
    assert {"symptom": "chest_pain", "keyword": "chest pain"} in matches
    assert {"symptom": "breathing_difficulty", "keyword": "breathing difficulty"} in matches
    # never silently affects the derived checklist itself — still exactly the same fields as before
    assert set(res.json()["symptom_checklist"]) == {"chest_pain", "breathing_difficulty"}


def test_no_matches_is_an_empty_list_not_missing(client):
    case_id = _create_case(client)
    res = client.post(
        f"/cases/{case_id}/assessment/voice",
        json={"transcript": "patient's daughter is on her way to the hospital", "language_code": "en"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["matched_keywords"] == []


# --------------------------------------------------------------- follow-up notes
def test_helper_can_add_a_follow_up_note(client):
    case_id = _create_case(client)
    res = client.post(
        f"/cases/{case_id}/notes",
        json={"author_id": "HLP-001", "text": "Family says patient just vomited blood"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["case_id"] == case_id
    assert body["author_id"] == "HLP-001"
    assert {"symptom": "vomiting", "keyword": "vomit"} in body["matched_keywords"]


def test_notes_never_touch_the_saved_assessment(client):
    case_id = _create_case(client)
    client.post(
        f"/cases/{case_id}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    client.post(f"/cases/{case_id}/notes", json={"author_id": "HLP-001", "text": "patient is now unconscious"})
    assessment = client.get(f"/cases/{case_id}/assessment").json()
    # a note mentioning "unconscious" never silently adds it to the saved checklist
    assert assessment["symptom_checklist"] == ["chest_pain"]


def test_notes_are_newest_first_and_all_returned(client):
    case_id = _create_case(client)
    client.post(f"/cases/{case_id}/notes", json={"author_id": "HLP-001", "text": "first update"})
    client.post(f"/cases/{case_id}/notes", json={"author_id": "HLP-001", "text": "second update"})
    notes = client.get(f"/cases/{case_id}/notes").json()
    assert len(notes) == 2
    assert notes[0]["text"] == "second update"
    assert notes[1]["text"] == "first update"


def test_notes_require_helper_role_not_just_case_access(client, client_factory):
    """Once a hospital is selected, its receptionist CAN see the case (passes
    the middleware's case-access check) but must still not be able to post a
    follow-up note — that channel is helper-authored only."""
    case_id = _create_case(client)
    client.post(
        f"/cases/{case_id}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    confirm_hospital(client, case_id, cls="economical")

    receptionist = client_factory("recep-hosp-001")
    res = receptionist.post(f"/cases/{case_id}/notes", json={"author_id": "recep-hosp-001", "text": "trying to add a note"})
    assert res.status_code == 403, res.text


def test_notes_endpoint_still_scoped_to_case_access(client_factory):
    """A helper with no relationship to this case at all is blocked by the
    same middleware scoping every other /cases/{id}/* route already gets."""
    admin = client_factory("admin")
    case_id = _create_case(admin, helper_id="HLP-001")

    other_helper = client_factory("HLP-002")
    assert other_helper.get(f"/cases/{case_id}/notes").status_code == 403
