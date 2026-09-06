"""FR-10 Control Room (Background Supervisor).

Proves the acceptance criteria:
  * a simulated stalled ambulance location produces an `anomaly` flag within the
    defined time window;
  * a simulated same-last-bed collision (Phase-4's mechanism) produces a
    `conflict` flag — the collision is not silently swallowed by the raw log;
  * a hospital bed-usage mismatch produces a `reconciliation` flag;
  * every flag is born `escalated` to a human contact, and the ONLY way a flag
    becomes `resolved` is the explicit human-resolve endpoint.
"""
from tests.helpers import confirm_hospital
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.assessment import Assessment, CriticalityLevel, InputMethod
from app.models.bed_lock import BedType, ConflictLog
from app.models.case import Case, CaseStatus, CreationPath
from app.models.control_room import Flag, FlagStatus
from app.models.hospital import Hospital
from app.services import bed_lock as bedlock_svc

BENGALURU = {"latitude": 12.97, "longitude": 77.59}


def _stale(minutes: int) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes)


def _bed_locked_case(client, symptoms=("chest_pain",), criticality="Serious") -> tuple[str, str]:
    """A Path-B case progressed to a confirmed hospital + active bed lock."""
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


def _make_race_case(db, case_id: str) -> None:
    db.add(Case(
        case_id=case_id, creation_path=CreationPath.B, next_of_kin_phone_number="9123456780",
        helper_id="HLP-002", gps_latitude=1.0, gps_longitude=1.0, gps_source="helper_device",
        status=CaseStatus.OPEN,
    ))
    db.add(Assessment(
        case_id=case_id, criticality_level=CriticalityLevel.SERIOUS,
        symptom_checklist=["chest_pain"], input_method=InputMethod.checklist,
    ))
    db.commit()


# --------------------------------------------------------------- 1. ANOMALY ----
def test_stalled_ambulance_location_produces_an_anomaly_flag(client, db_session):
    cid, hid = _bed_locked_case(client)

    # simulate the ambulance/helper device going silent 20 min ago (>10 min window)
    case = db_session.get(Case, cid)
    case.gps_timestamp = _stale(20)
    db_session.commit()

    scan = client.post("/control-room/scan").json()
    assert len(scan["anomaly_flag_ids"]) == 1

    flags = client.get("/control-room/flags?flag_type=anomaly").json()
    assert len(flags) == 1
    f = flags[0]
    assert f["flag_type"] == "anomaly"
    assert f["status"] == "escalated"
    assert "@" in f["escalated_to"]
    assert f["related_case_ids"] == [cid]
    assert f["related_hospital_id"] == hid
    assert "not updated" in f["details"]
    assert f["resolved_at"] is None


def test_fresh_in_transit_case_is_not_an_anomaly(client):
    _bed_locked_case(client)  # gps_timestamp + selection are "now"
    scan = client.post("/control-room/scan").json()
    assert scan["anomaly_flag_ids"] == []


def test_re_scanning_does_not_duplicate_an_open_anomaly_flag(client, db_session):
    cid, _ = _bed_locked_case(client)
    db_session.get(Case, cid).gps_timestamp = _stale(20)
    db_session.commit()

    first = client.post("/control-room/scan").json()
    assert len(first["anomaly_flag_ids"]) == 1
    second = client.post("/control-room/scan").json()
    assert second["anomaly_flag_ids"] == []  # idempotent while still open

    assert db_session.scalar(select(func.count()).select_from(Flag)) == 1


# --------------------------------------------------------------- 2. CONFLICT ---
def test_same_last_bed_collision_produces_a_conflict_flag(client, db_session):
    db_session.add(Hospital(
        hospital_id="HOSP-ONEBED", name="One Bed Clinic", specialties=["emergency", "cardiology"],
        live_bed_count=1, live_icu_count=0, distance_km=1.0, eta_minutes=5, rating=4.0,
        cost_tier="Government-Low", accepted_schemes=[],
    ))
    db_session.commit()
    _make_race_case(db_session, "CASE-X")
    _make_race_case(db_session, "CASE-Y")

    # Phase-4 mechanism: the loser gets a BedLockConflict AND a conflict_log row.
    bedlock_svc.acquire_lock(db_session, "HOSP-ONEBED", "CASE-X", BedType.general)
    with pytest.raises(bedlock_svc.BedLockConflict):
        bedlock_svc.acquire_lock(db_session, "HOSP-ONEBED", "CASE-Y", BedType.general)
    assert db_session.scalar(select(func.count()).select_from(ConflictLog)) == 1

    scan = client.post("/control-room/scan").json()
    assert len(scan["conflict_flag_ids"]) == 1

    flags = client.get("/control-room/flags?flag_type=conflict").json()
    assert len(flags) == 1
    f = flags[0]
    assert f["flag_type"] == "conflict"
    assert f["status"] == "escalated"
    assert set(f["related_case_ids"]) == {"CASE-X", "CASE-Y"}
    assert f["related_hospital_id"] == "HOSP-ONEBED"

    # the conflict_log is immutable -> never re-promoted
    assert client.post("/control-room/scan").json()["conflict_flag_ids"] == []


# --------------------------------------------------------- 3. RECONCILIATION ---
def test_bed_usage_mismatch_produces_a_reconciliation_flag(client):
    _cid, hid = _bed_locked_case(client)  # platform now holds 1 active general lock at hid

    # hospital's own live count says nothing is reserved -> disagreement
    r = client.put(
        f"/hospitals/{hid}/reported-bed-usage",
        json={"reported_general_in_use": 0, "reported_icu_in_use": 0},
    )
    assert r.status_code == 200

    scan = client.post("/control-room/scan").json()
    assert len(scan["reconciliation_flag_ids"]) == 1

    flags = client.get("/control-room/flags?flag_type=reconciliation").json()
    assert len(flags) == 1
    f = flags[0]
    assert f["flag_type"] == "reconciliation"
    assert f["status"] == "escalated"
    assert f["related_hospital_id"] == hid
    assert "disagrees" in f["details"]


def test_matching_bed_report_produces_no_flag(client):
    _cid, hid = _bed_locked_case(client)
    client.put(
        f"/hospitals/{hid}/reported-bed-usage",
        json={"reported_general_in_use": 1, "reported_icu_in_use": 0},
    )
    scan = client.post("/control-room/scan").json()
    assert scan["reconciliation_flag_ids"] == []


def test_receptionist_can_only_report_their_own_hospital(client_factory):
    recep = client_factory("recep-hosp-001")  # linked to HOSP-001
    assert recep.put(
        "/hospitals/HOSP-001/reported-bed-usage",
        json={"reported_general_in_use": 2, "reported_icu_in_use": 1},
    ).status_code == 200
    assert recep.put(
        "/hospitals/HOSP-004/reported-bed-usage",
        json={"reported_general_in_use": 0, "reported_icu_in_use": 0},
    ).status_code == 403


# ------------------------------------------------- escalation + human resolve --
def test_every_flag_is_born_escalated_to_a_human_never_open_or_resolved(client, db_session):
    cid, hid = _bed_locked_case(client)
    db_session.get(Case, cid).gps_timestamp = _stale(20)
    db_session.commit()
    client.put(
        f"/hospitals/{hid}/reported-bed-usage",
        json={"reported_general_in_use": 5, "reported_icu_in_use": 0},
    )
    client.post("/control-room/scan")

    flags = client.get("/control-room/flags?include_resolved=true").json()
    assert len(flags) == 2
    for f in flags:
        assert f["status"] == "escalated"          # never 'open'
        assert f["escalated_to"] and "@" in f["escalated_to"]
        assert f["resolved_at"] is None
        assert f["resolved_by"] is None


def test_resolve_endpoint_is_the_only_path_to_resolved_status(client, db_session):
    cid, _ = _bed_locked_case(client)
    db_session.get(Case, cid).gps_timestamp = _stale(20)
    db_session.commit()
    fid = client.post("/control-room/scan").json()["anomaly_flag_ids"][0]

    # the system leaves it escalated, even across repeated scans
    assert client.get(f"/control-room/flags/{fid}").json()["status"] == "escalated"
    client.post("/control-room/scan")
    assert client.get(f"/control-room/flags/{fid}").json()["status"] == "escalated"

    # explicit human action resolves it
    res = client.post(
        f"/control-room/flags/{fid}/resolve", json={"resolution_note": "driver phoned in, all fine"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "resolved"
    assert body["resolved_by"] == "admin"
    assert body["resolved_at"] is not None
    assert body["resolution_note"] == "driver phoned in, all fine"

    # resolving again is rejected
    assert client.post(f"/control-room/flags/{fid}/resolve", json={}).status_code == 409
    # unknown flag -> 404
    assert client.post("/control-room/flags/nope/resolve", json={}).status_code == 404

    # resolved flags leave the default dashboard, still visible in history
    assert fid not in [f["flag_id"] for f in client.get("/control-room/flags").json()]
    assert fid in [
        f["flag_id"] for f in client.get("/control-room/flags?include_resolved=true").json()
    ]


def test_only_control_room_resolve_service_assigns_resolved_status():
    """FR-10 hard rule: nothing but control_room.resolve_flag() writes 'resolved'."""
    import pathlib
    import re

    assign_re = re.compile(r"\.status\s*=\s*(FlagStatus\.resolved|['\"]resolved['\"])")
    app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for py in app_dir.rglob("*.py"):
        for i, line in enumerate(py.read_text().splitlines(), 1):
            if assign_re.search(line):
                rel = py.relative_to(app_dir.parent).as_posix()
                if rel == "app/services/control_room.py":
                    continue
                offenders.append(f"{rel}:{i}: {line.strip()}")
    assert not offenders, f"unexpected 'resolved' assignments: {offenders}"


def test_control_room_endpoints_are_staff_only(client_factory):
    recep = client_factory("recep-hosp-001")
    assert recep.post("/control-room/scan").status_code == 403
    assert recep.get("/control-room/flags").status_code == 403

    anon = client_factory(None)
    assert anon.post("/control-room/scan").status_code == 401


def test_scan_reports_nothing_on_a_quiet_pipeline(client):
    scan = client.post("/control-room/scan").json()
    assert scan == {
        "anomaly_flag_ids": [],
        "conflict_flag_ids": [],
        "reconciliation_flag_ids": [],
        "total": 0,
    }
