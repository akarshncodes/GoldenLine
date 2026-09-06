"""FR-1 On-Scene Assessment — checklist path, voice-stub path, mandatory confirm."""

BENGALURU = {"latitude": 12.97, "longitude": 77.59}

VOICE_LINE = "Male, roughly 60, severe chest pain and breathing difficulty"


def _create_case(client) -> str:
    res = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"name": "Asha", "approx_age": 60, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["case_id"]


# ------------------------------------------------------------- checklist path ---
def test_checklist_submission_saves(client):
    case_id = _create_case(client)
    res = client.post(
        f"/cases/{case_id}/assessment/checklist",
        json={
            "criticality_level": "Serious",
            "symptom_checklist": ["chest_pain", "breathing_difficulty"],
            "confirm": True,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["input_method"] == "checklist"
    assert body["criticality_level"] == "Serious"
    assert sorted(body["symptom_checklist"]) == ["breathing_difficulty", "chest_pain"]
    assert body["raw_voice_transcript"] is None

    got = client.get(f"/cases/{case_id}/assessment")
    assert got.status_code == 200
    assert got.json()["assessment_id"] == body["assessment_id"]


def test_checklist_requires_confirm_true(client):
    case_id = _create_case(client)
    res = client.post(
        f"/cases/{case_id}/assessment/checklist",
        json={
            "criticality_level": "Stable",
            "symptom_checklist": ["high_fever"],
            "confirm": False,
        },
    )
    assert res.status_code == 422
    assert client.get(f"/cases/{case_id}/assessment").status_code == 404  # nothing saved


def test_unknown_symptom_tag_rejected(client):
    case_id = _create_case(client)
    res = client.post(
        f"/cases/{case_id}/assessment/checklist",
        json={"criticality_level": "Stable", "symptom_checklist": ["heart_attack"], "confirm": True},
    )
    assert res.status_code == 422


# ----------------------------------------------------------------- voice path ---
def test_voice_stub_prefills_but_does_not_save(client):
    case_id = _create_case(client)
    res = client.post(
        f"/cases/{case_id}/assessment/voice",
        json={"transcript": VOICE_LINE, "language_code": "en"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["saved"] is False
    assert set(body["symptom_checklist"]) == {"chest_pain", "breathing_difficulty"}
    assert body["criticality_level"] == "Critical"  # "severe" keyword
    assert body["raw_voice_transcript"] == VOICE_LINE

    # nothing persisted yet
    assert client.get(f"/cases/{case_id}/assessment").status_code == 404


def test_voice_then_confirm_saves(client):
    case_id = _create_case(client)
    derived = client.post(
        f"/cases/{case_id}/assessment/voice",
        json={"transcript": VOICE_LINE, "language_code": "en"},
    ).json()

    res = client.post(
        f"/cases/{case_id}/assessment/confirm",
        json={
            "criticality_level": derived["criticality_level"],
            "symptom_checklist": derived["symptom_checklist"],
            "raw_voice_transcript": derived["raw_voice_transcript"],
            "confirm": True,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["input_method"] == "voice"
    assert body["raw_voice_transcript"] == VOICE_LINE

    got = client.get(f"/cases/{case_id}/assessment").json()
    assert got["input_method"] == "voice"
    assert set(got["symptom_checklist"]) == {"chest_pain", "breathing_difficulty"}


def test_voice_confirm_requires_confirm_true(client):
    case_id = _create_case(client)
    res = client.post(
        f"/cases/{case_id}/assessment/confirm",
        json={
            "criticality_level": "Critical",
            "symptom_checklist": ["chest_pain"],
            "raw_voice_transcript": VOICE_LINE,
            "confirm": False,
        },
    )
    assert res.status_code == 422
    assert client.get(f"/cases/{case_id}/assessment").status_code == 404


def test_unsupported_language_rejected(client):
    case_id = _create_case(client)
    res = client.post(
        f"/cases/{case_id}/assessment/voice",
        json={"transcript": VOICE_LINE, "language_code": "fr"},
    )
    assert res.status_code == 422


# --------------------------------------------------------------- safety rules ---
def test_no_diagnosis_free_text_field_accepted(client):
    """FRP FR-1: there must be no free-text diagnosis field. extra keys are rejected."""
    case_id = _create_case(client)
    for path, extra in [
        ("checklist", {"criticality_level": "Serious", "symptom_checklist": ["trauma"], "confirm": True, "diagnosis": "internal bleeding"}),
        ("voice", {"transcript": VOICE_LINE, "language_code": "en", "diagnosis": "MI"}),
        ("confirm", {"criticality_level": "Serious", "symptom_checklist": ["trauma"], "raw_voice_transcript": VOICE_LINE, "confirm": True, "diagnosis": "MI"}),
    ]:
        res = client.post(f"/cases/{case_id}/assessment/{path}", json=extra)
        assert res.status_code == 422, f"{path} accepted an extra field: {res.text}"


# --------------------------------------------------------------- integration ----
def test_assessment_against_missing_case_is_rejected(client):
    res = client.post(
        "/cases/does-not-exist/assessment/checklist",
        json={"criticality_level": "Stable", "symptom_checklist": ["high_fever"], "confirm": True},
    )
    assert res.status_code == 404


def test_reassessment_updates_in_place_one_to_one(client):
    case_id = _create_case(client)
    first = client.post(
        f"/cases/{case_id}/assessment/checklist",
        json={"criticality_level": "Stable", "symptom_checklist": ["high_fever"], "confirm": True},
    ).json()
    second = client.post(
        f"/cases/{case_id}/assessment/checklist",
        json={"criticality_level": "Critical", "symptom_checklist": ["seizure"], "confirm": True},
    ).json()

    assert first["assessment_id"] == second["assessment_id"]
    got = client.get(f"/cases/{case_id}/assessment").json()
    assert got["criticality_level"] == "Critical"
    assert got["symptom_checklist"] == ["seizure"]
