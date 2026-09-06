"""FR-6 Hospital Pre-Arrival Preparation — baseline + symptom-based, explicit confirm."""
from tests.helpers import confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}

BASELINE_KEYS = {"prepare_bed", "notify_general_duty_staff", "check_standard_equipment"}


def _bed_locked_case(client, symptoms=("chest_pain",), criticality="Serious") -> tuple[str, str]:
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 55, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": criticality, "symptom_checklist": list(symptoms), "confirm": True},
    )
    hid = confirm_hospital(client, cid).json()["selected_hospital_id"]
    return cid, hid


def _actions(client, case_id):
    return client.get(f"/cases/{case_id}/prep-actions").json()


# --------------------------------------------------------------- baseline ------
def test_every_bed_locked_case_gets_exactly_three_pending_baseline_actions(client):
    cid, hid = _bed_locked_case(client, symptoms=["high_fever"])  # no symptom-based match
    body = _actions(client, cid)

    assert body["confirmed"] == []
    baseline = [a for a in body["pending"] if a["action_type"] == "baseline"]
    assert len(baseline) == 3
    assert {a["action_key"] for a in baseline} == BASELINE_KEYS
    assert all(a["status"] == "pending" for a in baseline)
    assert all(a["hospital_id"] == hid for a in baseline)
    # high_fever is not in the FR-6 lookup table -> no symptom-based actions
    assert [a for a in body["pending"] if a["action_type"] == "symptom_based"] == []


# ---------------------------------------------------------- symptom-based ------
def test_chest_pain_adds_cardiology_standby_and_absence_does_not(client):
    with_cp, _ = _bed_locked_case(client, symptoms=["chest_pain"])
    keys = {a["action_key"] for a in _actions(client, with_cp)["pending"]}
    assert "cardiology_standby" in keys
    cardio = next(a for a in _actions(client, with_cp)["pending"] if a["action_key"] == "cardiology_standby")
    assert cardio["action_type"] == "symptom_based"
    assert cardio["triggered_by_symptom"] == "chest_pain"
    assert cardio["suggested_department"] == "cardiology"

    without_cp, _ = _bed_locked_case(client, symptoms=["high_fever"])
    assert "cardiology_standby" not in {a["action_key"] for a in _actions(client, without_cp)["pending"]}


def test_bleeding_adds_two_actions_and_bleeding_plus_trauma_dedupes(client):
    cid, _ = _bed_locked_case(client, symptoms=["visible_bleeding", "trauma"])
    keys = [a["action_key"] for a in _actions(client, cid)["pending"] if a["action_type"] == "symptom_based"]
    # blood_bank_alert + surgical_standby, each once despite both symptoms mapping to them
    assert sorted(keys) == ["blood_bank_alert", "surgical_standby"]


def test_breathing_difficulty_adds_oxygen_check(client):
    cid, _ = _bed_locked_case(client, symptoms=["breathing_difficulty"])
    keys = {a["action_key"] for a in _actions(client, cid)["pending"]}
    assert "oxygen_ventilator_check" in keys


# --------------------------------------------------------------- confirm -------
def test_confirming_one_action_does_not_touch_the_others(client):
    cid, _ = _bed_locked_case(client, symptoms=["chest_pain"])
    before = _actions(client, cid)["pending"]
    assert len(before) == 4  # 3 baseline + cardiology_standby

    target = next(a for a in before if a["action_key"] == "prepare_bed")
    res = client.post(
        f"/prep-actions/{target['prep_action_id']}/confirm",
        json={"receptionist_id": "RECEP-1"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "confirmed"
    assert body["confirmed_by"] == "RECEP-1"
    assert body["confirmed_at"] is not None

    after = _actions(client, cid)
    assert len(after["confirmed"]) == 1
    assert after["confirmed"][0]["action_key"] == "prepare_bed"
    assert len(after["pending"]) == 3
    assert all(a["status"] == "pending" and a["confirmed_by"] is None for a in after["pending"])


def test_double_confirm_is_rejected(client):
    cid, _ = _bed_locked_case(client)
    aid = _actions(client, cid)["pending"][0]["prep_action_id"]
    assert client.post(f"/prep-actions/{aid}/confirm", json={"receptionist_id": "R"}).status_code == 200
    assert client.post(f"/prep-actions/{aid}/confirm", json={"receptionist_id": "R"}).status_code == 409


def test_confirm_unknown_action_404(client):
    assert client.post("/prep-actions/nope/confirm", json={"receptionist_id": "R"}).status_code == 404


# ------------------------------------------------------- the hard rule --------
def test_only_the_confirm_service_assigns_confirmed_status(client):
    """FR-6 hard rule: a prep_action must never become 'confirmed' automatically.

    Scan for any ASSIGNMENT of a confirmed status to a `.status` attribute. The
    only legitimate one lives in app/services/prep.py::confirm().
    """
    import pathlib
    import re

    assign_re = re.compile(
        r"\.status\s*=\s*(PrepActionStatus\.confirmed|['\"]confirmed['\"])"
    )
    app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for py in app_dir.rglob("*.py"):
        for i, line in enumerate(py.read_text().splitlines(), 1):
            if assign_re.search(line):
                rel = py.relative_to(app_dir.parent).as_posix()
                if rel == "app/services/prep.py":
                    continue
                offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, f"unexpected 'confirmed' assignments: {offenders}"


def test_generate_is_idempotent(client):
    cid, _ = _bed_locked_case(client, symptoms=["chest_pain"])
    n1 = len(_actions(client, cid)["pending"])
    # a second GET must not create more rows
    n2 = len(_actions(client, cid)["pending"])
    assert n1 == n2 == 4
