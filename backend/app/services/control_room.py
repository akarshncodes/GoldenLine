"""FR-10 Control Room — the three background checks + the human-only resolve path.

This module only OBSERVES data other phases produce:
  * ANOMALY WATCHING     -> scans active in-transit cases for a stalled ambulance
                            location or a case that has gone quiet.
  * CONFLICT RESOLUTION   -> promotes Phase-4 `conflict_logs` rows to proper
                            `conflict` flags (they must not live only in the raw log).
  * DATA RECONCILIATION   -> compares a hospital's self-reported bed usage against
                            the platform's expectation (active bed locks).

It never mutates cases, locks or hospitals — it raises `Flag` rows and escalates.

Scheduling: there is no real scheduler yet. `run_all_checks()` is invoked by the
manually-triggerable POST /control-room/scan endpoint; a cron/APScheduler job
would call the same function on an interval.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import (
    CONTROL_ROOM_CASE_QUIET_MINUTES,
    CONTROL_ROOM_ESCALATION_CONTACT,
    CONTROL_ROOM_LOCATION_STALL_MINUTES,
)
from app.models.bed_lock import BedLock, ConflictLog, LockStatus
from app.models.case import Case, CaseStatus
from app.models.control_room import Flag, FlagStatus, FlagType
from app.models.hospital_bed_report import HospitalBedReport

logger = logging.getLogger(__name__)

# A case is "in transit" once a hospital is selected and until it is admitted.
_TERMINAL_STATUSES = (CaseStatus.ADMITTED, CaseStatus.DISCHARGED)


class FlagError(Exception):
    """Bad resolve request (unknown flag, or already resolved)."""


# --------------------------------------------------------------- datetime utils
def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive_utc(dt: datetime | None) -> datetime | None:
    """Normalise to naive UTC. ORM reads come back naive, raw-SQL reads tz-aware
    (project-overview gotcha #1) — level them before any comparison."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


# --------------------------------------------------------------- flag creation
def _open_flag_for(db: Session, dedup_key: str) -> Flag | None:
    return db.scalar(
        select(Flag).where(Flag.dedup_key == dedup_key, Flag.status != FlagStatus.resolved)
    )


def _any_flag_for(db: Session, dedup_key: str) -> Flag | None:
    return db.scalar(select(Flag).where(Flag.dedup_key == dedup_key))


def create_flag(
    db: Session,
    *,
    flag_type: FlagType,
    details: str,
    related_case_ids: list[str] | None = None,
    related_hospital_id: str | None = None,
    dedup_key: str | None = None,
) -> Flag:
    """Create a flag. It is ALWAYS escalated to the human contact on creation —
    there is deliberately no parameter to create it `open` or `resolved`."""
    flag = Flag(
        flag_type=flag_type,
        related_case_ids=list(related_case_ids or []),
        related_hospital_id=related_hospital_id,
        details=details,
        dedup_key=dedup_key,
        status=FlagStatus.escalated,          # never 'open', never 'resolved'
        escalated_to=CONTROL_ROOM_ESCALATION_CONTACT,
    )
    db.add(flag)
    db.flush()
    logger.warning(
        "CONTROL ROOM %s flag %s escalated to %s: %s",
        flag_type.value, flag.flag_id, CONTROL_ROOM_ESCALATION_CONTACT, details,
    )
    return flag


# --------------------------------------------------------------- 1. ANOMALIES
def check_anomalies(db: Session) -> list[Flag]:
    now = _now()
    stall = timedelta(minutes=CONTROL_ROOM_LOCATION_STALL_MINUTES)
    quiet = timedelta(minutes=CONTROL_ROOM_CASE_QUIET_MINUTES)
    created: list[Flag] = []

    active = db.scalars(
        select(Case).where(
            Case.selected_hospital_id.is_not(None),
            Case.status.not_in(_TERMINAL_STATUSES),
        )
    ).all()

    for case in active:
        dedup_key = f"anomaly:{case.case_id}"
        if _open_flag_for(db, dedup_key):
            continue  # already flagged and not yet resolved by a human

        loc_at = _naive_utc(case.gps_timestamp)
        activity_stamps = [
            _naive_utc(case.gps_timestamp),
            _naive_utc(case.selection_timestamp),
            _naive_utc(case.created_at),
        ]
        last_activity = max(d for d in activity_stamps if d is not None)

        reason: str | None = None
        if loc_at is None:
            if now - last_activity > stall:
                age_min = int((now - last_activity).total_seconds() // 60)
                reason = (
                    "ambulance location has never been reported for this in-transit "
                    f"case ({age_min} min since the hospital was selected)"
                )
        elif now - loc_at > stall:
            stale_min = int((now - loc_at).total_seconds() // 60)
            reason = (
                f"ambulance location has not updated in {stale_min} min "
                f"(threshold {CONTROL_ROOM_LOCATION_STALL_MINUTES} min)"
            )
        elif now - last_activity > quiet:
            quiet_min = int((now - last_activity).total_seconds() // 60)
            reason = (
                f"case has gone quiet mid-transit — no update in {quiet_min} min "
                f"(threshold {CONTROL_ROOM_CASE_QUIET_MINUTES} min)"
            )

        if reason:
            created.append(
                create_flag(
                    db,
                    flag_type=FlagType.anomaly,
                    details=f"case {case.case_id}: {reason}",
                    related_case_ids=[case.case_id],
                    related_hospital_id=case.selected_hospital_id,
                    dedup_key=dedup_key,
                )
            )
    return created


# --------------------------------------------------------------- 2. CONFLICTS
def check_conflicts(db: Session) -> list[Flag]:
    """Promote every Phase-4 bed-lock collision to a proper `conflict` flag.

    `conflict_logs` rows are immutable, so once a flag exists for one (resolved
    or not) we never re-create it."""
    created: list[Flag] = []
    for cl in db.scalars(select(ConflictLog).order_by(ConflictLog.detected_at)):
        dedup_key = f"conflict:{cl.conflict_log_id}"
        if _any_flag_for(db, dedup_key):
            continue

        bed_type = cl.bed_type.value if hasattr(cl.bed_type, "value") else cl.bed_type
        cases = [c for c in (cl.case_id_a, cl.case_id_b) if c]
        detected = _naive_utc(cl.detected_at)
        details = (
            f"bed-lock collision at {cl.hospital_id}: cases {cl.case_id_a} and "
            f"{cl.case_id_b} raced for the last {bed_type} bed. The system held the "
            f"bed for one case and logged the loser (conflict_log {cl.conflict_log_id}, "
            f"detected {detected:%Y-%m-%d %H:%M:%S} UTC) — a human must confirm the "
            f"loser was re-routed."
        )
        created.append(
            create_flag(
                db,
                flag_type=FlagType.conflict,
                details=details,
                related_case_ids=cases,
                related_hospital_id=cl.hospital_id,
                dedup_key=dedup_key,
            )
        )
    return created


# --------------------------------------------------------------- 3. RECONCILIATION
def _platform_expected_in_use(db: Session) -> dict[str, dict[str, int]]:
    """{hospital_id: {'general': n_active_locks, 'ICU': n_active_locks}}."""
    rows = db.execute(
        select(BedLock.hospital_id, BedLock.bed_type, func.count())
        .where(BedLock.lock_status == LockStatus.active)
        .group_by(BedLock.hospital_id, BedLock.bed_type)
    ).all()
    out: dict[str, dict[str, int]] = {}
    for hid, bt, n in rows:
        btv = bt.value if hasattr(bt, "value") else bt
        out.setdefault(hid, {})[btv] = n
    return out


def check_reconciliation(db: Session) -> list[Flag]:
    created: list[Flag] = []
    expected = _platform_expected_in_use(db)

    for report in db.scalars(select(HospitalBedReport)):
        exp = expected.get(report.hospital_id, {})
        exp_general = exp.get("general", 0)
        exp_icu = exp.get("ICU", 0)

        if (
            report.reported_general_in_use == exp_general
            and report.reported_icu_in_use == exp_icu
        ):
            continue  # hospital's live count agrees with the platform

        dedup_key = f"reconciliation:{report.hospital_id}"
        if _open_flag_for(db, dedup_key):
            continue

        reported_at = _naive_utc(report.reported_at)
        details = (
            f"hospital {report.hospital_id} reported bed usage disagrees with the "
            f"platform: platform holds {exp_general} general + {exp_icu} ICU active "
            f"bed-lock(s)/admission(s), hospital reports {report.reported_general_in_use} "
            f"general + {report.reported_icu_in_use} ICU in use (hospital report at "
            f"{reported_at:%Y-%m-%d %H:%M:%S} UTC). A bed may have been given away "
            f"outside the platform, or an admission not recorded."
        )
        created.append(
            create_flag(
                db,
                flag_type=FlagType.reconciliation,
                details=details,
                related_hospital_id=report.hospital_id,
                dedup_key=dedup_key,
            )
        )
    return created


# --------------------------------------------------------------- orchestration
@dataclass
class ScanResult:
    anomaly_flag_ids: list[str] = field(default_factory=list)
    conflict_flag_ids: list[str] = field(default_factory=list)
    reconciliation_flag_ids: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            len(self.anomaly_flag_ids)
            + len(self.conflict_flag_ids)
            + len(self.reconciliation_flag_ids)
        )


def run_all_checks(db: Session) -> ScanResult:
    """Run all three checks and commit any flags raised, in one transaction."""
    anomalies = check_anomalies(db)
    conflicts = check_conflicts(db)
    reconciliations = check_reconciliation(db)
    db.commit()
    return ScanResult(
        anomaly_flag_ids=[f.flag_id for f in anomalies],
        conflict_flag_ids=[f.flag_id for f in conflicts],
        reconciliation_flag_ids=[f.flag_id for f in reconciliations],
    )


# --------------------------------------------------------------- reads
def list_flags(
    db: Session,
    *,
    include_resolved: bool = False,
    flag_type: FlagType | None = None,
) -> list[Flag]:
    q = select(Flag).order_by(Flag.created_at.desc())
    if not include_resolved:
        q = q.where(Flag.status != FlagStatus.resolved)
    if flag_type is not None:
        q = q.where(Flag.flag_type == flag_type)
    return list(db.scalars(q))


def get_flag(db: Session, flag_id: str) -> Flag | None:
    return db.get(Flag, flag_id)


# --------------------------------------------------------------- THE resolve path
def resolve_flag(
    db: Session, *, flag_id: str, resolved_by: str, note: str | None = None
) -> Flag:
    """The ONLY path to status='resolved'. Requires a human actor (`resolved_by`).

    Nothing in the automated checks calls this — it is wired exclusively to
    POST /control-room/flags/{id}/resolve.
    """
    flag = db.get(Flag, flag_id)
    if flag is None:
        raise FlagError(f"flag '{flag_id}' does not exist")
    if not resolved_by:
        raise FlagError("a human resolver id is required")
    if flag.status == FlagStatus.resolved:
        raise FlagError(f"flag '{flag_id}' is already resolved")

    flag.status = FlagStatus.resolved
    flag.resolved_at = _now()
    flag.resolved_by = resolved_by
    flag.resolution_note = note
    db.commit()
    db.refresh(flag)
    logger.info("CONTROL ROOM flag %s resolved by human %s", flag_id, resolved_by)
    return flag
