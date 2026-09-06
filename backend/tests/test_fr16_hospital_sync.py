"""FR-16 Hospital Data Sync.

Acceptance criteria:
  * a hospital on `manual_counter` and a hospital on the `hms_api` stub both feed
    the SAME FR-2 ranking query (`bed_count_by_type` == the ranking inputs);
  * confirming an admission via QR handoff (FR-7) decrements the RIGHT hospital's
    live bed count, traceable to that exact handoff event.
"""
from tests.helpers import confirm_hospital
from sqlalchemy import select

from app.models.hospital import Hospital
from app.models.hospital_sync import HospitalSyncEvent

BENGALURU = {"latitude": 12.97, "longitude": 77.59}


def _case_needing(client, symptoms, criticality="Serious") -> str:
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"approx_age": 40, "gender": "male"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": criticality, "symptom_checklist": list(symptoms), "confirm": True},
    )
    return cid


def _bed_locked_case(client, symptoms=("chest_pain",), criticality="Serious") -> tuple[str, str]:
    cid = _case_needing(client, symptoms, criticality)
    hid = confirm_hospital(client, cid).json()["selected_hospital_id"]
    return cid, hid


# --------------------------------------------------------------- tiers + config
def test_seed_hospitals_have_a_sync_tier(client):
    rows = client.get("/hospitals").json()
    tiers = {h["hospital_id"]: h["hospital_sync_tier"] for h in rows}
    assert tiers["HOSP-001"] == "hms_api"
    assert tiers["HOSP-007"] == "manual_counter"
    assert set(tiers.values()) == {"hms_api", "google_sheets", "manual_counter"}
    # bed_count_by_type mirrors the two legacy columns
    h1 = next(h for h in rows if h["hospital_id"] == "HOSP-001")
    assert h1["bed_count_by_type"] == {"general": h1["live_bed_count"], "ICU": h1["live_icu_count"]}


# ------------------- the required test: two tiers -> one ranking structure -----
def test_manual_and_hms_tiers_both_feed_the_same_ranking_query(client, db_session):
    # HOSP-007 (manual_counter) — two one-tap increments on general beds
    for _ in range(2):
        r = client.post("/hospitals/HOSP-007/beds/adjust", json={"bed_type": "general", "delta": 1})
        assert r.status_code == 200, r.text

    # HOSP-001 (hms_api) — pull from the mocked HMS (feed: general 9, ICU 3)
    r = client.post("/hospitals/HOSP-001/sync/hms")
    assert r.status_code == 200, r.text
    assert r.json()["bed_count_by_type"] == {"general": 9, "ICU": 3}

    db_session.expire_all()
    h7 = db_session.get(Hospital, "HOSP-007")
    h1 = db_session.get(Hospital, "HOSP-001")
    assert h7.bed_count_by_type["general"] == 55 + 2   # seed 55 + 2 taps
    assert h1.bed_count_by_type == {"general": 9, "ICU": 3}
    assert h7.last_synced_at is not None and h1.last_synced_at is not None

    # both hospitals carry general_medicine -> both qualify for a high_fever case,
    # and the ranking reads the SAME structure both tiers wrote into
    cid = _case_needing(client, ["high_fever"])
    ranked = {h["hospital_id"]: h for h in client.get(f"/cases/{cid}/hospital-ranking").json()["ranked"]}
    assert ranked["HOSP-007"]["live_bed_count"] == 57
    assert ranked["HOSP-001"]["live_bed_count"] == 9
    # availability (net of any active locks) is derived from the same counts
    assert ranked["HOSP-007"]["available_general_beds"] == 57
    assert ranked["HOSP-001"]["available_general_beds"] == 9


# ------------------- the required test: QR handoff decrements the right one ----
def test_qr_handoff_admission_decrements_the_admitting_hospital(client, db_session):
    cid, hid = _bed_locked_case(client, symptoms=["chest_pain"], criticality="Serious")  # general bed
    db_session.expire_all()
    before = db_session.get(Hospital, hid).live_bed_count
    other_id = next(h for h in ("HOSP-001", "HOSP-004", "HOSP-009") if h != hid)
    other_before = db_session.get(Hospital, other_id).live_bed_count

    tok = client.post(f"/cases/{cid}/qr-handoff").json()["token"]
    scan = client.post(
        "/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "NURSE-9"}
    )
    assert scan.status_code == 200, scan.text

    db_session.expire_all()
    assert db_session.get(Hospital, hid).live_bed_count == before - 1
    assert db_session.get(Hospital, hid).last_synced_at is not None
    assert db_session.get(Hospital, other_id).live_bed_count == other_before  # untouched

    # traceable to THIS exact handoff event
    ev = db_session.scalar(
        select(HospitalSyncEvent).where(HospitalSyncEvent.related_case_id == cid)
    )
    assert ev is not None
    assert ev.source == "qr_handoff_admission"
    assert ev.hospital_id == hid
    assert ev.bed_type == "general"
    assert ev.general_before == before and ev.general_after == before - 1
    assert ev.related_handoff_token_id is not None
    assert ev.actor == "NURSE-9"

    # the fulfilled reservation is released, so availability didn't drop twice
    dash = client.get("/hospitals/dashboard").json()
    row = next(r for r in dash if r["hospital_id"] == hid)
    assert row["available_general_beds"] == before - 1
    assert row["active_general_locks"] == 0


def test_admission_decrements_once_and_discharge_gives_the_bed_back(client, db_session):
    cid, hid = _bed_locked_case(client)          # Serious -> general bed
    db_session.expire_all()
    baseline = db_session.get(Hospital, hid).live_bed_count

    tok = client.post(f"/cases/{cid}/qr-handoff").json()["token"]
    client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "N"})
    db_session.expire_all()
    assert db_session.get(Hospital, hid).live_bed_count == baseline - 1

    # a second scan of the (used) token can't decrement again
    client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "N"})
    db_session.expire_all()
    assert db_session.get(Hospital, hid).live_bed_count == baseline - 1

    # discharge is a distinct, explicit, audited event that returns the bed
    client.post(f"/cases/{cid}/trigger-discharge")
    db_session.expire_all()
    assert db_session.get(Hospital, hid).live_bed_count == baseline

    events = db_session.scalars(
        select(HospitalSyncEvent)
        .where(HospitalSyncEvent.related_case_id == cid)
        .order_by(HospitalSyncEvent.created_at)
    ).all()
    assert [e.source for e in events] == ["qr_handoff_admission", "discharge_bed_released"]
    assert events[1].bed_type == "general"
    assert events[1].general_before == baseline - 1 and events[1].general_after == baseline

    # discharging is idempotent for the bed credit (guarded 409 on 2nd call anyway)
    client.post(f"/cases/{cid}/trigger-discharge")
    db_session.expire_all()
    again = db_session.scalars(
        select(HospitalSyncEvent).where(
            HospitalSyncEvent.related_case_id == cid,
            HospitalSyncEvent.source == "discharge_bed_released",
        )
    ).all()
    assert len(again) == 1


# --------------------------------------------------------------- tier guards ---
def test_sync_endpoint_rejects_the_wrong_tier(client):
    # HOSP-007 is manual_counter, not hms_api
    r = client.post("/hospitals/HOSP-007/sync/hms")
    assert r.status_code == 409
    # HOSP-001 is hms_api, not manual_counter
    r = client.post("/hospitals/HOSP-001/beds/adjust", json={"bed_type": "general", "delta": 1})
    assert r.status_code == 409


def test_manual_counter_is_one_tap_only(client):
    assert client.post(
        "/hospitals/HOSP-007/beds/adjust", json={"bed_type": "general", "delta": 3}
    ).status_code == 422
    assert client.post(
        "/hospitals/HOSP-007/beds/adjust", json={"bed_type": "wards", "delta": 1}
    ).status_code == 422


def test_manual_counter_floors_at_zero(client, db_session):
    h = db_session.get(Hospital, "HOSP-010")  # manual_counter
    seed_icu = h.live_icu_count
    for _ in range(seed_icu + 3):  # decrement well past zero
        client.post("/hospitals/HOSP-010/beds/adjust", json={"bed_type": "ICU", "delta": -1})
    db_session.expire_all()
    assert db_session.get(Hospital, "HOSP-010").live_icu_count == 0


def test_google_sheets_demo_url_reads_counts_from_the_query(client, db_session):
    # HOSP-002 is google_sheets; a demo URL carries ?general=&icu= (no network call)
    r = client.post(
        "/hospitals/HOSP-002/sync/sheet",
        json={"sheet_url": "https://sheets.example/hosp2?general=4&icu=1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["bed_count_by_type"] == {"general": 4, "ICU": 1}
    db_session.expire_all()
    h = db_session.get(Hospital, "HOSP-002")
    assert h.bed_count_by_type == {"general": 4, "ICU": 1}
    assert h.last_synced_at is not None


def test_google_sheets_real_export_path(client, db_session, monkeypatch):
    """A real docs.google.com sheet URL is fetched via the CSV export and parsed."""
    import app.services.hospital_sync as hs

    real_id = "1" + "A" * 43  # realistic 44-char id
    captured = {}

    class _Resp:
        text = "label,count\ngeneral,7\nICU,2\n"

        def raise_for_status(self): ...

    def fake_get(url, **kw):
        captured["url"] = url
        return _Resp()

    monkeypatch.setattr(hs.httpx, "get", fake_get)
    r = client.post(
        "/hospitals/HOSP-002/sync/sheet",
        json={"sheet_url": f"https://docs.google.com/spreadsheets/d/{real_id}/edit"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["bed_count_by_type"] == {"general": 7, "ICU": 2}
    assert captured["url"] == f"https://docs.google.com/spreadsheets/d/{real_id}/export?format=csv"
    assert "live Google Sheets sync" in r.json()["event"]["note"]


def test_hms_real_api_path(client, db_session, monkeypatch):
    """When HMS_API_BASE_URL is set, the HMS tier does a real GET."""
    import app.services.hospital_sync as hs
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("HMS_API_BASE_URL", "https://hms.example/api")

    class _Resp:
        def raise_for_status(self): ...
        def json(self): return {"general": 11, "ICU": 4}

    seen = {}

    def fake_get(url, **kw):
        seen["url"] = url
        return _Resp()

    monkeypatch.setattr(hs.httpx, "get", fake_get)
    r = client.post("/hospitals/HOSP-001/sync/hms")
    get_settings.cache_clear()  # don't leak the env override to other tests

    assert r.status_code == 200, r.text
    assert r.json()["bed_count_by_type"] == {"general": 11, "ICU": 4}
    assert seen["url"] == "https://hms.example/api/hospitals/HOSP-001/beds"
    assert "live HMS API sync" in r.json()["event"]["note"]


def test_last_synced_at_is_set_regardless_of_tier(client, db_session):
    client.post("/hospitals/HOSP-007/beds/adjust", json={"bed_type": "general", "delta": 1})
    client.post("/hospitals/HOSP-001/sync/hms")
    client.post(
        "/hospitals/HOSP-004/sync/sheet",
        json={"sheet_url": "https://sheet.example/x?general=5&icu=2"},
    )
    db_session.expire_all()
    for hid in ("HOSP-007", "HOSP-001", "HOSP-004"):
        assert db_session.get(Hospital, hid).last_synced_at is not None


# --------------------------------------------------------------- RBAC ----------
def test_receptionist_can_only_sync_their_own_hospital(client_factory):
    recep7 = client_factory("recep-hosp-007")  # HOSP-007, manual_counter
    assert recep7.post(
        "/hospitals/HOSP-007/beds/adjust", json={"bed_type": "general", "delta": 1}
    ).status_code == 200
    assert recep7.post(
        "/hospitals/HOSP-001/beds/adjust", json={"bed_type": "general", "delta": 1}
    ).status_code == 403
    assert recep7.post("/hospitals/HOSP-001/sync/hms").status_code == 403

    coord = client_factory("coord-bb-01")  # blood bank coordinator
    assert coord.post(
        "/hospitals/HOSP-007/beds/adjust", json={"bed_type": "general", "delta": 1}
    ).status_code == 403

    anon = client_factory(None)
    assert anon.get("/hospitals/HOSP-007/sync-status").status_code == 401


def test_only_admin_can_change_a_hospitals_sync_tier(client, client_factory):
    recep7 = client_factory("recep-hosp-007")
    assert recep7.put(
        "/hospitals/HOSP-007/sync-tier", json={"hospital_sync_tier": "hms_api"}
    ).status_code == 403

    r = client.put(
        "/hospitals/HOSP-003/sync-tier",
        json={"hospital_sync_tier": "google_sheets", "sheet_url": "https://sheet.example/h3?general=7&icu=2"},
    )
    assert r.status_code == 200
    assert r.json()["hospital_sync_tier"] == "google_sheets"
    # now the sheet tier works for HOSP-003
    assert client.post("/hospitals/HOSP-003/sync/sheet", json={}).json()["bed_count_by_type"] == {
        "general": 7, "ICU": 2
    }


def test_sync_status_lists_recent_events(client):
    client.post("/hospitals/HOSP-007/beds/adjust", json={"bed_type": "general", "delta": 1})
    client.post("/hospitals/HOSP-007/beds/adjust", json={"bed_type": "ICU", "delta": -1})
    body = client.get("/hospitals/HOSP-007/sync-status").json()
    assert body["hospital_sync_tier"] == "manual_counter"
    assert body["last_synced_at"] is not None
    assert len(body["recent_events"]) == 2
    assert {e["source"] for e in body["recent_events"]} == {"manual_counter"}
