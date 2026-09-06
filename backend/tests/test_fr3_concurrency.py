"""FR-3 item 7 — two simultaneous lock requests for the same last bed:
only one wins, the other gets a conflict AND a conflict_log row is written.
"""
import threading

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.database import Base, apply_sqlite_pragmas
from app.models.assessment import Assessment, CriticalityLevel, InputMethod
from app.models.bed_lock import BedLock, ConflictLog, LockStatus
from app.models.case import Case, CaseStatus, CreationPath
from app.models.hospital import Hospital
from app.services import bed_lock as svc
from app.services.hospital_seed import seed_hospitals


@pytest.fixture()
def Session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'conc.db'}", connect_args={"check_same_thread": False}
    )
    apply_sqlite_pragmas(engine)
    Base.metadata.create_all(engine)
    maker = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with maker() as s:
        seed_hospitals(s)
    yield maker
    engine.dispose()


def _make_case(s, case_id: str) -> None:
    s.add(Case(
        case_id=case_id, creation_path=CreationPath.B, next_of_kin_phone_number="9123456780",
        helper_id="HLP-002", gps_latitude=1.0, gps_longitude=1.0, gps_source="helper_device",
        status=CaseStatus.OPEN,
    ))
    s.add(Assessment(
        case_id=case_id, criticality_level=CriticalityLevel.SERIOUS,
        symptom_checklist=["chest_pain"], input_method=InputMethod.checklist,
    ))


def test_two_threads_race_for_the_last_general_bed(Session):
    hospital_id = "HOSP-RACE"
    with Session() as s:
        s.add(Hospital(
            hospital_id=hospital_id, name="One Bed Clinic", specialties=["emergency", "cardiology"],
            live_bed_count=1, live_icu_count=0, distance_km=1.0, eta_minutes=5, rating=4.0,
            cost_tier="Government-Low", accepted_schemes=[],
        ))
        _make_case(s, "CASE-A")
        _make_case(s, "CASE-B")
        s.commit()

    results: dict[str, str] = {}
    barrier = threading.Barrier(2)

    def worker(case_id: str) -> None:
        with Session() as s:
            barrier.wait()  # line both requests up as closely as possible
            try:
                svc.acquire_lock(s, hospital_id, case_id, svc.BedType.general)
                results[case_id] = "locked"
            except svc.BedLockConflict:
                results[case_id] = "conflict"

    threads = [threading.Thread(target=worker, args=(c,)) for c in ("CASE-A", "CASE-B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # exactly one winner, one loser
    assert sorted(results.values()) == ["conflict", "locked"]

    with Session() as s:
        active = s.scalar(
            select(func.count()).select_from(BedLock).where(BedLock.lock_status == LockStatus.active)
        )
        conflicts = s.scalars(select(ConflictLog)).all()
        assert active == 1                       # only one bed actually held
        assert len(conflicts) == 1               # the collision was captured
        c = conflicts[0]
        assert c.hospital_id == hospital_id
        assert c.bed_type == svc.BedType.general
        assert {c.case_id_a, c.case_id_b} == {"CASE-A", "CASE-B"}


def test_many_threads_never_oversubscribe_two_beds(Session):
    hospital_id = "HOSP-2BED"
    with Session() as s:
        s.add(Hospital(
            hospital_id=hospital_id, name="Two Bed Clinic", specialties=["emergency"],
            live_bed_count=2, live_icu_count=0, distance_km=1.0, eta_minutes=5, rating=4.0,
            cost_tier="Government-Low", accepted_schemes=[],
        ))
        for i in range(8):
            _make_case(s, f"C{i}")
        s.commit()

    results: dict[str, str] = {}
    barrier = threading.Barrier(8)

    def worker(case_id: str) -> None:
        with Session() as s:
            barrier.wait()
            try:
                svc.acquire_lock(s, hospital_id, case_id, svc.BedType.general)
                results[case_id] = "locked"
            except svc.BedLockConflict:
                results[case_id] = "conflict"

    threads = [threading.Thread(target=worker, args=(f"C{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert list(results.values()).count("locked") == 2
    assert list(results.values()).count("conflict") == 6
    with Session() as s:
        active = s.scalar(
            select(func.count()).select_from(BedLock).where(BedLock.lock_status == LockStatus.active)
        )
        assert active == 2
