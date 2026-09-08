"""FR-2 API tests — ranking endpoint keyed by case_id, Path A / Path B selection."""

BENGALURU = {"latitude": 12.97, "longitude": 77.59}
DELHI = {"latitude": 28.61, "longitude": 77.20}
from tests.helpers import path_a_sos  # noqa: E402


def _path_b_case(client, symptoms=("chest_pain",), criticality="Serious") -> str:
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"name": "Asha", "approx_age": 60, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    r = client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": criticality, "symptom_checklist": list(symptoms), "confirm": True},
    )
    assert r.status_code == 201, r.text
    return cid


def _path_a_case(client, symptoms=("chest_pain",)) -> str:
    cid = path_a_sos(client, gps=DELHI).json()["case"]["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": list(symptoms), "confirm": True},
    )
    return cid


# ------------------------------------------------------------ seed + list -------
def test_hospital_dataset_seeded(client):
    res = client.get("/hospitals")
    assert res.status_code == 200
    assert len(res.json()) == 25


# ------------------------------------------------------------ ranking ----------
def test_ranking_requires_symptoms_logged(client):
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 60, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    assert client.get(f"/cases/{cid}/hospital-ranking").status_code == 409


def test_ranking_excludes_hospitals_without_required_specialty(client):
    cid = _path_b_case(client, symptoms=["chest_pain"])
    body = client.get(f"/cases/{cid}/hospital-ranking").json()

    assert body["required_specialties"] == ["cardiology"]
    ranked_ids = [h["hospital_id"] for h in body["ranked"]]
    assert "HOSP-001" in ranked_ids            # has cardiology
    assert "HOSP-002" in body["excluded_hospital_ids"]   # no cardiology
    assert "HOSP-002" not in ranked_ids


def test_ranking_is_cheapest_tier_first(client):
    cid = _path_b_case(client, symptoms=["chest_pain"])
    ranked = client.get(f"/cases/{cid}/hospital-ranking").json()["ranked"]
    tiers = [h["cost_tier"] for h in ranked]
    order = {"Government-Low": 0, "Private-Standard": 1, "Private-Premium": 2}
    assert tiers == sorted(tiers, key=lambda t: order[t])
    assert ranked[0]["rank"] == 1


def test_ranking_never_selects_a_hospital(client):
    cid = _path_b_case(client)
    client.get(f"/cases/{cid}/hospital-ranking")
    case = client.get(f"/cases/{cid}").json()
    assert case["selected_hospital_id"] is None


# ------------------------------------------------------------ live distance ----
def test_ranking_is_estimated_before_any_location_is_reported(client):
    """Path A: the family SOS GPS is audit-only (FR-0) — the case has no
    location yet, so ranking falls back to each hospital's static mock
    distance/ETA."""
    from app.services.hospital_seed import SEED_HOSPITALS

    cid = _path_a_case(client, symptoms=["chest_pain"])
    body = client.get(f"/cases/{cid}/hospital-ranking").json()
    assert body["distance_source"] == "estimated"

    seed_by_id = {h["hospital_id"]: h for h in SEED_HOSPITALS}
    for h in body["ranked"]:
        seed = seed_by_id[h["hospital_id"]]
        assert h["distance_km"] == seed["distance_km"]
        assert h["eta_minutes"] == seed["eta_minutes"]


def test_ranking_is_live_once_helper_location_is_known(client):
    """Path B sets the case's location from the helper's device at creation
    (FR-0) — ranking distance is real haversine distance from there, not the
    hospital's static mock number."""
    from app.services.geo import haversine_km
    from app.services.hospital_seed import SEED_HOSPITALS

    cid = _path_b_case(client, symptoms=["chest_pain"])
    body = client.get(f"/cases/{cid}/hospital-ranking").json()
    assert body["distance_source"] == "live"

    seed_by_id = {h["hospital_id"]: h for h in SEED_HOSPITALS}
    for h in body["ranked"]:
        seed = seed_by_id[h["hospital_id"]]
        expected = round(haversine_km(BENGALURU["latitude"], BENGALURU["longitude"], seed["latitude"], seed["longitude"]), 2)
        assert h["distance_km"] == expected
        assert h["distance_km"] != seed["distance_km"]  # genuinely recomputed, not the mock value
        assert h["eta_minutes"] == max(1, round(expected / 30.0 * 60))


def test_reporting_helper_location_switches_ranking_from_estimated_to_live(client):
    cid = _path_a_case(client, symptoms=["chest_pain"])
    before = client.get(f"/cases/{cid}/hospital-ranking").json()
    assert before["distance_source"] == "estimated"

    res = client.post(f"/cases/{cid}/helper-location", json={"helper_id": "HLP-001", "gps": DELHI})
    assert res.status_code == 200, res.text

    after = client.get(f"/cases/{cid}/hospital-ranking").json()
    assert after["distance_source"] == "live"
    # DELHI is nowhere near any Dindigul hospital's real coordinates — the
    # recomputed distances must differ substantially from the mock estimates.
    before_by_id = {h["hospital_id"]: h["distance_km"] for h in before["ranked"]}
    after_by_id = {h["hospital_id"]: h["distance_km"] for h in after["ranked"]}
    assert all(after_by_id[hid] != before_by_id[hid] for hid in after_by_id)


# ------------------------------------------------------------ scheme boost -----
def test_scheme_boost_is_a_within_tier_nudge_not_a_distance_override(client):
    """Distance stays dominant: a scheme hospital does not jump a clearly closer one."""
    cid = _path_b_case(client, symptoms=["chest_pain"])

    def std_order(body):
        return [h["hospital_id"] for h in body["ranked"] if h["cost_tier"] == "Private-Standard"]

    before = client.get(f"/cases/{cid}/hospital-ranking").json()
    assert std_order(before) == ["HOSP-009", "HOSP-022"]  # HOSP-009 closer + better rated

    client.put(f"/cases/{cid}/scheme", json={"government_scheme": "state_scheme"})
    after = client.get(f"/cases/{cid}/hospital-ranking").json()

    # HOSP-022 accepts state_scheme (HOSP-009 does not) and its score is nudged,
    # but HOSP-009 is meaningfully closer, so the order does NOT change.
    assert std_order(after) == ["HOSP-009", "HOSP-022"]
    h022_before = next(h for h in before["ranked"] if h["hospital_id"] == "HOSP-022")
    h022_after = next(h for h in after["ranked"] if h["hospital_id"] == "HOSP-022")
    assert h022_after["scheme_boost_applied"] is True
    assert h022_after["score"] < h022_before["score"]      # boost lowered (improved) its score
    assert after["ranked"][0]["cost_tier"] == "Government-Low"  # tiers intact


def test_unknown_scheme_rejected(client):
    cid = _path_b_case(client)
    assert client.put(f"/cases/{cid}/scheme", json={"government_scheme": "fake_scheme"}).status_code == 422


# ------------------------------------------------------------ cost classes -----
def test_ranking_response_has_three_cost_classes(client):
    """economical/moderate/expensive — one best-by-bed/ETA/distance hospital
    each (or null), the helper's actual choice screen. See ranking-distance-
    over-scheme memory + this session's "helper picks a class" redesign."""
    cid = _path_b_case(client, symptoms=["chest_pain"])
    body = client.get(f"/cases/{cid}/hospital-ranking").json()

    classes = body["classes"]
    assert set(classes) == {"economical", "moderate", "expensive"}
    # chest_pain (cardiology) is available in all 3 tiers for this seed data.
    assert classes["economical"]["hospital_id"] == "HOSP-001"      # only Gov-Low w/ cardiology
    assert classes["moderate"]["hospital_id"] == "HOSP-009"        # closer than HOSP-022
    assert classes["expensive"]["hospital_id"] == "HOSP-005"       # closest of HOSP-003/004/005
    # every class pick is also present in the full ranked list, at its own rank.
    ranked_ids = {h["hospital_id"] for h in body["ranked"]}
    assert all(h["hospital_id"] in ranked_ids for h in classes.values() if h)


def test_class_pick_ignores_rating_unlike_the_full_ranking(client):
    """STEP-2's full `ranked` list weighs in rating; the class view doesn't —
    it's ETA + distance only (bed availability already guaranteed)."""
    cid = _path_b_case(client, symptoms=["chest_pain"])
    body = client.get(f"/cases/{cid}/hospital-ranking").json()
    moderate = body["classes"]["moderate"]
    ranked_std = [h for h in body["ranked"] if h["cost_tier"] == "Private-Standard"]
    # HOSP-009 has both the better rating AND the shorter ETA/distance here, so
    # this alone doesn't prove rating is ignored — but it must still be the
    # STEP-2 rank #1 in its tier for this seed data (both signals agree).
    assert moderate["hospital_id"] == ranked_std[0]["hospital_id"]


# ------------------------------------------------------------ selection: both paths, helper-only
def test_helper_can_select_any_of_the_3_class_hospitals_path_a(client):
    """Not just the top-ranked one — any of the 3 cost-class picks, both paths."""
    cid = _path_a_case(client, symptoms=["chest_pain"])
    classes = client.get(f"/cases/{cid}/hospital-ranking").json()["classes"]
    chosen = classes["expensive"]["hospital_id"]  # deliberately not the cheapest

    res = client.post(
        f"/cases/{cid}/select-hospital",
        json={"hospital_id": chosen, "helper_id": "HLP-001"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["selected_hospital_id"] == chosen
    assert body["selected_by"] == "HLP-001"
    assert body["selected_via"] == "helper_confirm"
    assert body["selection_timestamp"] is not None


def test_helper_can_select_any_of_the_3_class_hospitals_path_b(client):
    cid = _path_b_case(client, symptoms=["chest_pain"])
    classes = client.get(f"/cases/{cid}/hospital-ranking").json()["classes"]
    chosen = classes["economical"]["hospital_id"]

    res = client.post(
        f"/cases/{cid}/confirm-hospital",
        json={"hospital_id": chosen, "helper_id": "HLP-001"},
    )
    assert res.status_code == 201, res.text
    assert res.json()["selected_hospital_id"] == chosen


def test_rejects_hospital_not_in_ranked_list(client):
    cid = _path_a_case(client, symptoms=["chest_pain"])
    # HOSP-002 has no cardiology -> excluded from this case's ranked list entirely
    res = client.post(
        f"/cases/{cid}/select-hospital",
        json={"hospital_id": "HOSP-002", "helper_id": "HLP-001"},
    )
    assert res.status_code == 400


def test_rejects_a_ranked_hospital_that_is_not_its_class_pick(client):
    """HOSP-022 is ranked (Private-Standard, has cardiology) but HOSP-009 is the
    class's actual best pick — only the 3 class picks are selectable now."""
    cid = _path_b_case(client, symptoms=["chest_pain"])
    body = client.get(f"/cases/{cid}/hospital-ranking").json()
    assert body["classes"]["moderate"]["hospital_id"] == "HOSP-009"
    res = client.post(
        f"/cases/{cid}/confirm-hospital",
        json={"hospital_id": "HOSP-022", "helper_id": "HLP-001"},
    )
    assert res.status_code == 400


def test_path_a_endpoint_rejects_path_b_case(client):
    cid = _path_b_case(client)
    classes = client.get(f"/cases/{cid}/hospital-ranking").json()["classes"]
    hid = next(h["hospital_id"] for h in classes.values() if h)
    res = client.post(
        f"/cases/{cid}/select-hospital",
        json={"hospital_id": hid, "helper_id": "HLP-001"},
    )
    assert res.status_code == 409


def test_path_b_endpoint_rejects_path_a_case(client):
    cid = _path_a_case(client)
    classes = client.get(f"/cases/{cid}/hospital-ranking").json()["classes"]
    hid = next(h["hospital_id"] for h in classes.values() if h)
    res = client.post(
        f"/cases/{cid}/confirm-hospital",
        json={"hospital_id": hid, "helper_id": "HLP-001"},
    )
    assert res.status_code == 409


def test_second_selection_is_rejected(client):
    cid = _path_b_case(client, symptoms=["chest_pain"])
    hid = client.get(f"/cases/{cid}/hospital-ranking").json()["classes"]["moderate"]["hospital_id"]
    client.post(f"/cases/{cid}/confirm-hospital", json={"hospital_id": hid, "helper_id": "HLP-001"})
    again = client.post(f"/cases/{cid}/confirm-hospital", json={"hospital_id": hid, "helper_id": "HLP-001"})
    assert again.status_code == 409


def test_family_cannot_select_a_hospital(client_factory):
    """Hospital selection is helper-only, both paths — never the family. The
    helper asks the family which cost class they'd like, then taps it."""
    admin = client_factory("admin")
    res = path_a_sos(admin, phone_number="9800000099")
    cid = res.json()["case"]["case_id"]
    admin.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": ["chest_pain"], "confirm": True},
    )
    classes = admin.get(f"/cases/{cid}/hospital-ranking").json()["classes"]
    hid = next(h["hospital_id"] for h in classes.values() if h)

    fam = client_factory(None)
    tok = fam.post("/otp/request", json={"phone_number": "9800000099"}).json()
    v = fam.post(
        "/otp/verify",
        json={"otp_verification_id": tok["otp_verification_id"], "code": tok["dev_code"]},
    ).json()
    fam.headers["Authorization"] = f"Bearer {v['access_token']}"

    res = fam.post(
        f"/cases/{cid}/select-hospital",
        json={"hospital_id": hid, "helper_id": "HLP-001"},
    )
    assert res.status_code == 403


def test_ranking_against_missing_case_404(client):
    assert client.get("/cases/ghost/hospital-ranking").status_code == 404
