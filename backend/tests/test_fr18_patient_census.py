"""FR-18 Patient Census + Manual Admit/Discharge/Bed-Assignment.

Acceptance criteria:
  * a hospital-wide census tracks patients independent of the emergency pipeline;
  * admitting a walk-in into a general/ICU bed reduces what FR-2 ranking / FR-3
    bed-lock see as available — the SAME live_bed_count/live_icu_count columns —
    with ZERO changes to hospital_ranking.py or bed_lock.py;
  * a walk-in admit can never double-book a bed an ambulance's bed-lock has
    already reserved (nor vice versa);
  * every QR-handoff-admitted case also shows up in the census, and its
    discharge closes out that census entry too — without double-decrementing
    or double-crediting the hospital's live bed count.
"""
import threading

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.database import Base, apply_sqlite_pragmas
from app.models.assessment import Assessment, CriticalityLevel, InputMethod
from app.models.case import Case, CaseStatus, CreationPath
from app.models.hospital import Hospital
from app.models.patient import Patient, PatientStatus, PatientType
from app.services import bed_lock as bed_lock_svc
from app.services import hospital_sync
from app.services import patients as patients_svc
from app.services.hospital_seed import seed_hospitals
from tests.helpers import confirm_hospital

BENGALURU = {"latitude": 12.97, "longitude": 77.59}


def _prepped_case(client, symptoms=("chest_pain",)) -> tuple[str, str]:
    cid = client.post(
        "/cases",
        json={
            "next_of_kin_phone_number": "9123456780",
            "patient": {"name": "Asha Rao", "approx_age": 58, "gender": "female"},
            "helper_id": "HLP-001",
            "helper_gps": BENGALURU,
        },
    ).json()["case_id"]
    client.post(
        f"/cases/{cid}/assessment/checklist",
        json={"criticality_level": "Serious", "symptom_checklist": list(symptoms), "confirm": True},
    )
    hid = confirm_hospital(client, cid).json()["selected_hospital_id"]
    return cid, hid


# --------------------------------------------------------------- basic CRUD ---
def test_create_and_list_patient(client):
    res = client.post(
        "/hospitals/HOSP-001/patients",
        json={"full_name": "Ravi Kumar", "approx_age": 45, "gender": "male", "patient_type": "walk_in"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["hospital_id"] == "HOSP-001"
    assert body["status"] == "waiting"
    assert body["patient_type"] == "walk_in"

    listed = client.get("/hospitals/HOSP-001/patients").json()
    assert any(p["patient_id"] == body["patient_id"] for p in listed)


def test_cannot_set_patient_type_emergency_case_directly(client):
    res = client.post(
        "/hospitals/HOSP-001/patients",
        json={"full_name": "X", "patient_type": "emergency_case"},
    )
    assert res.status_code == 422  # not in the Literal["walk_in","scheduled"] allowed set


def test_unknown_hospital_404s(client):
    res = client.post("/hospitals/HOSP-999/patients", json={"full_name": "X"})
    assert res.status_code == 404


def test_receptionist_scoped_to_own_hospital(client_factory):
    recep1 = client_factory("recep-hosp-001")
    recep4 = client_factory("recep-hosp-004")

    ok = recep1.post("/hospitals/HOSP-001/patients", json={"full_name": "Local Patient"})
    assert ok.status_code == 200

    forbidden = recep4.post("/hospitals/HOSP-001/patients", json={"full_name": "X"})
    assert forbidden.status_code == 403


# --------------------------------------------------- admit/discharge lifecycle
def test_admit_and_discharge_lifecycle(client):
    p = client.post("/hospitals/HOSP-001/patients", json={"full_name": "Walk In"}).json()
    admitted = client.post(f"/patients/{p['patient_id']}/admit", json={"category_code": "general"})
    assert admitted.status_code == 200
    assignment = admitted.json()
    assert assignment["status"] == "active"
    assert assignment["category_code"] == "general"

    patient = client.get(f"/patients/{p['patient_id']}").json()
    assert patient["status"] == "admitted"

    discharged = client.post(f"/patients/{p['patient_id']}/discharge")
    assert discharged.status_code == 200
    assert discharged.json()["status"] == "released"
    assert client.get(f"/patients/{p['patient_id']}").json()["status"] == "discharged"


def test_cannot_admit_twice(client):
    p = client.post("/hospitals/HOSP-001/patients", json={"full_name": "X"}).json()
    client.post(f"/patients/{p['patient_id']}/admit", json={"category_code": "general"})
    again = client.post(f"/patients/{p['patient_id']}/admit", json={"category_code": "general"})
    assert again.status_code == 409


def test_cannot_discharge_without_active_assignment(client):
    p = client.post("/hospitals/HOSP-001/patients", json={"full_name": "X"}).json()
    res = client.post(f"/patients/{p['patient_id']}/discharge")
    assert res.status_code == 409


def test_admit_into_fr17_category_never_touches_live_bed_counts(client):
    client.put("/hospitals/HOSP-001/bed-categories/private", json={"label": "Private", "total_beds": 3})
    before = client.get("/hospitals").json()
    h1_before = next(h for h in before if h["hospital_id"] == "HOSP-001")

    p = client.post("/hospitals/HOSP-001/patients", json={"full_name": "X"}).json()
    res = client.post(f"/patients/{p['patient_id']}/admit", json={"category_code": "private"})
    assert res.status_code == 200

    after = client.get("/hospitals").json()
    h1_after = next(h for h in after if h["hospital_id"] == "HOSP-001")
    assert h1_after["live_bed_count"] == h1_before["live_bed_count"]
    assert h1_after["live_icu_count"] == h1_before["live_icu_count"]


# ------------------------- THE critical availability-integration regression ---
def test_walkin_admission_reduces_ranking_availability_by_exactly_one(client):
    before = client.get("/hospitals").json()
    h1_before = next(h for h in before if h["hospital_id"] == "HOSP-001")
    general_before = h1_before["live_bed_count"]

    p = client.post("/hospitals/HOSP-001/patients", json={"full_name": "Walk In"}).json()
    admit_res = client.post(f"/patients/{p['patient_id']}/admit", json={"category_code": "general"})
    assert admit_res.status_code == 200

    after = client.get("/hospitals").json()
    h1_after = next(h for h in after if h["hospital_id"] == "HOSP-001")
    assert h1_after["live_bed_count"] == general_before - 1
    assert h1_after["bed_count_by_type"]["general"] == general_before - 1

    # discharge restores it, with ZERO changes needed to hospital_ranking.py/bed_lock.py
    discharge_res = client.post(f"/patients/{p['patient_id']}/discharge")
    assert discharge_res.status_code == 200
    restored = client.get("/hospitals").json()
    h1_restored = next(h for h in restored if h["hospital_id"] == "HOSP-001")
    assert h1_restored["live_bed_count"] == general_before


def test_walkin_discharge_is_idempotent(client):
    p = client.post("/hospitals/HOSP-001/patients", json={"full_name": "X"}).json()
    client.post(f"/patients/{p['patient_id']}/admit", json={"category_code": "general"})
    first = client.get("/hospitals").json()
    h1 = next(h for h in first if h["hospital_id"] == "HOSP-001")
    general_after_admit = h1["live_bed_count"]

    client.post(f"/patients/{p['patient_id']}/discharge")
    # a second discharge call 409s (no active assignment) — the bed can't be
    # credited back twice via the API surface
    again = client.post(f"/patients/{p['patient_id']}/discharge")
    assert again.status_code == 409

    final = client.get("/hospitals").json()
    h1_final = next(h for h in final if h["hospital_id"] == "HOSP-001")
    assert h1_final["live_bed_count"] == general_after_admit + 1


def test_no_bed_available_conflict(client):
    # HOSP-003 is small in the Dindigul seed data; drain it via manual_adjust down to 0
    hosp = client.get("/hospitals").json()
    h3 = next(h for h in hosp if h["hospital_id"] == "HOSP-003")
    for _ in range(h3["live_bed_count"]):
        client.post("/hospitals/HOSP-003/beds/adjust", json={"bed_type": "general", "delta": -1})

    p = client.post("/hospitals/HOSP-003/patients", json={"full_name": "X"}).json()
    res = client.post(f"/patients/{p['patient_id']}/admit", json={"category_code": "general"})
    assert res.status_code == 409


# ----------------------------- emergency-pipeline census hooks (integration) ---
def test_qr_handoff_admission_creates_census_entry_without_double_decrement(client):
    cid, hid = _prepped_case(client)
    before = client.get("/hospitals").json()
    h_before = next(h for h in before if h["hospital_id"] == hid)

    tok = client.post(f"/cases/{cid}/qr-handoff").json()["token"]
    client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "NURSE-1"})

    after = client.get("/hospitals").json()
    h_after = next(h for h in after if h["hospital_id"] == hid)
    # the bed count decremented exactly ONCE (via record_admission_decrement,
    # not a second time via the census hook)
    assert h_after["live_bed_count"] == h_before["live_bed_count"] - 1

    census = client.get(f"/hospitals/{hid}/patients").json()
    entry = next((p for p in census if p.get("linked_case_id") == cid), None)
    assert entry is not None
    assert entry["patient_type"] == "emergency_case"
    assert entry["status"] == "admitted"

    # re-scanning (already admitted) does not create a second census row nor
    # decrement again
    client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "NURSE-1"})
    census2 = client.get(f"/hospitals/{hid}/patients").json()
    assert sum(1 for p in census2 if p.get("linked_case_id") == cid) == 1


def test_discharge_closes_out_the_case_census_entry(client):
    cid, hid = _prepped_case(client)
    tok = client.post(f"/cases/{cid}/qr-handoff").json()["token"]
    client.post("/qr-handoff/scan", json={"case_id": cid, "token": tok, "scanned_by": "NURSE-1"})

    before = client.get("/hospitals").json()
    h_before = next(h for h in before if h["hospital_id"] == hid)

    client.post(f"/cases/{cid}/trigger-discharge")

    after = client.get("/hospitals").json()
    h_after = next(h for h in after if h["hospital_id"] == hid)
    assert h_after["live_bed_count"] == h_before["live_bed_count"] + 1

    census = client.get(f"/hospitals/{hid}/patients").json()
    entry = next(p for p in census if p.get("linked_case_id") == cid)
    assert entry["status"] == "discharged"


def test_admin_only_unscoped_patient_list(client, client_factory):
    client.post("/hospitals/HOSP-001/patients", json={"full_name": "A"})
    client.post("/hospitals/HOSP-004/patients", json={"full_name": "B"})

    res = client.get("/patients")
    assert res.status_code == 200
    hospital_ids = {p["hospital_id"] for p in res.json()}
    assert {"HOSP-001", "HOSP-004"}.issubset(hospital_ids)

    recep = client_factory("recep-hosp-001")
    assert recep.get("/patients").status_code == 403


# ----------------------------------------------------------- concurrency proof
@pytest.fixture()
def Session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'fr18-conc.db'}", connect_args={"check_same_thread": False}
    )
    apply_sqlite_pragmas(engine)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with maker() as s:
        seed_hospitals(s)
    yield maker
    engine.dispose()


def test_walkin_admit_cannot_double_book_a_bed_an_ambulance_case_has_reserved(Session):
    """The regression this whole design decision exists for: a hospital with
    exactly ONE general bed, a walk-in admit and an ambulance's bed-lock acquire
    racing for it — exactly one must win, never both."""
    hospital_id = "HOSP-RACE-FR18"
    with Session() as s:
        s.add(Hospital(
            hospital_id=hospital_id, name="One Bed Clinic", specialties=["emergency"],
            live_bed_count=1, live_icu_count=0, distance_km=1.0, eta_minutes=5, rating=4.0,
            cost_tier="Government-Low", accepted_schemes=[],
        ))
        s.add(Case(
            case_id="CASE-RACE", creation_path=CreationPath.B, next_of_kin_phone_number="9123456780",
            helper_id="HLP-002", gps_latitude=1.0, gps_longitude=1.0, gps_source="helper_device",
            status=CaseStatus.OPEN,
        ))
        s.add(Assessment(
            case_id="CASE-RACE", criticality_level=CriticalityLevel.SERIOUS,
            symptom_checklist=["chest_pain"], input_method=InputMethod.checklist,
        ))
        s.add(Patient(
            hospital_id=hospital_id, full_name="Walk In",
            patient_type=PatientType.walk_in, status=PatientStatus.waiting,
        ))
        s.commit()
        walkin_patient_id = s.scalar(select(Patient.patient_id).where(Patient.hospital_id == hospital_id))

    results: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def do_walkin() -> None:
        with Session() as s:
            barrier.wait()
            try:
                patients_svc.admit(s, walkin_patient_id, category_code="general", bed_label=None, actor="recep-test")
                results["walkin"] = "admitted"
            except hospital_sync.NoBedAvailable:
                results["walkin"] = "conflict"

    def do_ambulance() -> None:
        with Session() as s:
            barrier.wait()
            try:
                bed_lock_svc.acquire_lock(s, hospital_id, "CASE-RACE", bed_lock_svc.BedType.general)
                results["ambulance"] = "locked"
            except bed_lock_svc.BedLockConflict:
                results["ambulance"] = "conflict"

    threads = [threading.Thread(target=do_walkin), threading.Thread(target=do_ambulance)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # exactly one of the two claimed the single bed
    winners = [k for k, v in results.items() if v in ("admitted", "locked")]
    assert len(winners) == 1

    with Session() as s:
        hospital = s.get(Hospital, hospital_id)
        active_locks = s.scalar(
            select(bed_lock_svc.BedLock.bed_lock_id).where(
                bed_lock_svc.BedLock.hospital_id == hospital_id,
                bed_lock_svc.BedLock.lock_status == bed_lock_svc.LockStatus.active,
            )
        )
        # invariant holds: total physical capacity never goes negative and
        # never gets both claimed AND separately reserved
        if results["walkin"] == "admitted":
            assert hospital.live_bed_count == 0
            assert active_locks is None  # ambulance correctly lost — no lock exists
        else:
            assert hospital.live_bed_count == 1  # untouched — walk-in lost
            assert active_locks is not None  # ambulance correctly won
