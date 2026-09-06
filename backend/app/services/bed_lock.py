"""FR-3 Bed Lock service: atomic acquire, release, availability, dashboard."""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.assessment import Assessment, CriticalityLevel
from app.models.bed_lock import BedLock, BedType, ConflictLog, LockStatus
from app.models.case import Case
from app.models.hospital import Hospital

_CAPACITY_COLUMN = {BedType.general: "live_bed_count", BedType.ICU: "live_icu_count"}


class BedLockConflict(Exception):
    """The bed could not be locked because capacity is exhausted."""

    def __init__(self, hospital_id: str, bed_type: BedType, holder_case_id: str | None):
        self.hospital_id = hospital_id
        self.bed_type = bed_type
        self.holder_case_id = holder_case_id
        super().__init__(
            f"no available {bed_type.value} bed at {hospital_id}"
            + (f" (held by case {holder_case_id})" if holder_case_id else "")
        )


class NoActiveLock(Exception):
    pass


def bed_type_for_criticality(criticality: CriticalityLevel) -> BedType:
    """Critical patients need an ICU slot; everyone else a general bed."""
    return BedType.ICU if criticality == CriticalityLevel.CRITICAL else BedType.general


def bed_type_for_case(db: Session, case: Case) -> BedType:
    crit = db.scalar(
        select(Assessment.criticality_level).where(Assessment.case_id == case.case_id)
    )
    return bed_type_for_criticality(crit) if crit is not None else BedType.general


def get_active_lock(db: Session, case_id: str) -> BedLock | None:
    return db.scalar(
        select(BedLock).where(
            BedLock.case_id == case_id, BedLock.lock_status == LockStatus.active
        )
    )


def acquire_lock(db: Session, hospital_id: str, case_id: str, bed_type: BedType) -> BedLock:
    """Atomically hold one bed/ICU slot for a case.

    The guard is a single `INSERT ... SELECT ... WHERE capacity > active_locks`
    statement: the database evaluates the capacity check and performs the insert
    as one indivisible operation, and SQLite serialises concurrent writers on its
    write lock. Two simultaneous callers can therefore never both succeed on the
    same last bed — the loser inserts zero rows.
    """
    # Drop any read snapshot from earlier queries in this session so the guarded
    # INSERT below runs against the latest committed state.
    db.rollback()

    lock_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    capacity_col = _CAPACITY_COLUMN[bed_type]

    stmt = text(
        f"""
        INSERT INTO bed_locks (bed_lock_id, hospital_id, case_id, bed_type, lock_status, locked_at)
        SELECT :lock_id, :hospital_id, :case_id, :bed_type, 'active', :now
        WHERE (
            SELECT h.{capacity_col} FROM hospitals h WHERE h.hospital_id = :hospital_id
        ) > (
            SELECT COUNT(*) FROM bed_locks bl
            WHERE bl.hospital_id = :hospital_id
              AND bl.bed_type = :bed_type
              AND bl.lock_status = 'active'
        )
        """
    )
    result = db.execute(
        stmt,
        {
            "lock_id": lock_id,
            "hospital_id": hospital_id,
            "case_id": case_id,
            "bed_type": bed_type.value,
            "now": now,
        },
    )

    if result.rowcount == 1:
        db.commit()
        return db.get(BedLock, lock_id)

    # Lost the race (or hospital is full). Record the collision, then fail loudly.
    db.rollback()
    holder_case_id = db.scalar(
        select(BedLock.case_id)
        .where(
            BedLock.hospital_id == hospital_id,
            BedLock.bed_type == bed_type,
            BedLock.lock_status == LockStatus.active,
        )
        .order_by(BedLock.locked_at.desc())
        .limit(1)
    )
    if holder_case_id is not None and holder_case_id != case_id:
        db.add(
            ConflictLog(
                case_id_a=case_id,
                case_id_b=holder_case_id,
                hospital_id=hospital_id,
                bed_type=bed_type,
            )
        )
        db.commit()
    raise BedLockConflict(hospital_id, bed_type, holder_case_id)


def release_lock(db: Session, case_id: str) -> BedLock:
    """Release the case's active hold. The bed becomes available again immediately
    (availability is derived from active locks)."""
    db.rollback()
    now = datetime.now(timezone.utc)
    result = db.execute(
        text(
            """
            UPDATE bed_locks SET lock_status = 'released', released_at = :now
            WHERE case_id = :case_id AND lock_status = 'active'
            """
        ),
        {"now": now, "case_id": case_id},
    )
    if result.rowcount == 0:
        db.rollback()
        raise NoActiveLock(f"case '{case_id}' has no active bed lock")
    db.commit()
    return db.scalar(
        select(BedLock)
        .where(BedLock.case_id == case_id, BedLock.lock_status == LockStatus.released)
        .order_by(BedLock.released_at.desc())
        .limit(1)
    )


# --------------------------------------------------------------- availability ---
@dataclass
class HospitalAvailability:
    hospital_id: str
    name: str
    total_general_beds: int
    total_icu_beds: int
    active_general_locks: int
    active_icu_locks: int
    # beds already turned into a real admission (QR-handoff or FR-18 walk-in),
    # i.e. total_*_beds - live_*_count — see Hospital.total_bed_count.
    occupied_general_beds: int = 0
    occupied_icu_beds: int = 0

    @property
    def reserved_general_beds(self) -> int:
        """Occupied + pending (not-yet-admitted) locks — total minus this is
        what's actually free for a NEW ambulance to claim."""
        return self.occupied_general_beds + self.active_general_locks

    @property
    def reserved_icu_beds(self) -> int:
        return self.occupied_icu_beds + self.active_icu_locks

    @property
    def available_general_beds(self) -> int:
        return self.total_general_beds - self.reserved_general_beds

    @property
    def available_icu_beds(self) -> int:
        return self.total_icu_beds - self.reserved_icu_beds


def _active_lock_counts(db: Session) -> dict[tuple[str, str], int]:
    rows = db.execute(
        select(BedLock.hospital_id, BedLock.bed_type, func.count())
        .where(BedLock.lock_status == LockStatus.active)
        .group_by(BedLock.hospital_id, BedLock.bed_type)
    ).all()
    return {(hid, bt.value if hasattr(bt, "value") else bt): n for hid, bt, n in rows}


def availability_for_all(db: Session) -> list[HospitalAvailability]:
    counts = _active_lock_counts(db)
    out: list[HospitalAvailability] = []
    for h in db.scalars(select(Hospital).order_by(Hospital.hospital_id)):
        out.append(
            HospitalAvailability(
                hospital_id=h.hospital_id,
                name=h.name,
                total_general_beds=h.total_bed_count,
                total_icu_beds=h.total_icu_bed_count,
                active_general_locks=counts.get((h.hospital_id, "general"), 0),
                active_icu_locks=counts.get((h.hospital_id, "ICU"), 0),
                # clamp at 0: a sync tier could in principle report MORE free
                # beds than the original fixed total (e.g. a real capacity
                # increase); never show a negative "occupied" from that.
                occupied_general_beds=max(0, h.total_bed_count - h.live_bed_count),
                occupied_icu_beds=max(0, h.total_icu_bed_count - h.live_icu_count),
            )
        )
    return out


def availability_map(db: Session) -> dict[str, dict[str, int]]:
    """{hospital_id: {'general': available, 'ICU': available}} — for ranking."""
    return {
        a.hospital_id: {"general": a.available_general_beds, "ICU": a.available_icu_beds}
        for a in availability_for_all(db)
    }


def active_locks_for_hospital(db: Session, hospital_id: str) -> list[BedLock]:
    return list(
        db.scalars(
            select(BedLock)
            .where(
                BedLock.hospital_id == hospital_id,
                BedLock.lock_status == LockStatus.active,
            )
            .order_by(BedLock.locked_at)
        )
    )


def list_conflicts(db: Session) -> list[ConflictLog]:
    return list(db.scalars(select(ConflictLog).order_by(ConflictLog.detected_at.desc())))
