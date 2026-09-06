"""FR-16 Hospital Data Sync.

Three tiers keep a hospital's bed counts current, most→least automated:
  1. hms_api        — `sync_from_hms(hospital_id)`        (real GET when
                       HMS_API_BASE_URL is set, else a labelled mock feed)
  2. google_sheets  — `sync_from_sheet(hospital_id, url)` (real CSV export read for
                       a docs.google.com sheet, else a demo URL-query parser)
  3. manual_counter — `manual_adjust(...)`                (a one-tap ±1 endpoint)
  (4) auto-decrement on a *confirmed admission* — `record_admission_decrement(...)`,
      called ONLY from `handoff.scan()` (FR-7), never inferred anywhere else.
  (5) re-increment on discharge — `record_discharge_increment(...)`, called ONLY
      from `feedback.trigger_discharge()` (FR-8); an explicit, audited event, not
      silent inference. The hospital's own tier stays authoritative.
  (6) FR-18 walk-in admit/discharge — `record_walkin_admission_decrement(...)` /
      `record_walkin_discharge_increment(...)`, called from `services/patients.py`
      when a hospital-wide-census patient is admitted into (or discharged from) a
      general/ICU bed outside the emergency pipeline. Atomically guarded against
      BOTH another simultaneous walk-in AND a pending ambulance's bed-lock
      reservation (checks live_count > active bed_locks of that type, not just
      > 0 — live_count is never decremented when a lock is merely reserved, only
      at QR-handoff admission, so a bare >0 check would double-book a bed an
      incoming ambulance already holds).

Every path funnels through `apply_bed_counts()`, which writes the SAME
`live_bed_count` / `live_icu_count` columns FR-2 ranking reads
(`Hospital.bed_count_by_type`), stamps `last_synced_at`, and appends a
`hospital_sync_events` audit row. There is no per-tier ranking logic.
"""
import csv
import io
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.hospital import Hospital, HospitalSyncTier
from app.models.hospital_sync import HospitalSyncEvent

logger = logging.getLogger(__name__)

# Which tier each seed hospital is on. Mirrored by migration 0019's backfill and
# guarded by tests/test_fr4_fr5_seed_parity.py.
SEED_SYNC_TIERS: dict[str, str] = {
    "HOSP-001": "hms_api",
    "HOSP-002": "google_sheets",
    "HOSP-003": "manual_counter",
    "HOSP-004": "google_sheets",
    "HOSP-005": "hms_api",
    "HOSP-006": "manual_counter",
    "HOSP-007": "manual_counter",
    "HOSP-008": "hms_api",
    "HOSP-009": "hms_api",
    "HOSP-010": "manual_counter",
    "HOSP-011": "manual_counter",
    "HOSP-012": "google_sheets",
    "HOSP-013": "hms_api",
    "HOSP-014": "manual_counter",
    "HOSP-015": "manual_counter",
    "HOSP-016": "google_sheets",
    "HOSP-017": "manual_counter",
    "HOSP-018": "hms_api",
    "HOSP-019": "manual_counter",
    "HOSP-020": "manual_counter",
    "HOSP-021": "google_sheets",
    "HOSP-022": "hms_api",
    "HOSP-023": "manual_counter",
    "HOSP-024": "manual_counter",
    "HOSP-025": "google_sheets",
}


class HospitalNotFound(Exception):
    pass


class SyncTierMismatch(Exception):
    """The endpoint's tier is not the tier this hospital is configured for."""


class BadManualAdjust(Exception):
    pass


class NoBedAvailable(Exception):
    """FR-18: a walk-in admit lost the race for (or found) the last general/ICU bed."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class SyncOutcome:
    hospital_id: str
    source: str
    bed_count_by_type: dict[str, int]
    last_synced_at: datetime
    event: HospitalSyncEvent


# --------------------------------------------------------------- the one writer
def _write_sync_event(
    db: Session,
    hospital: Hospital,
    *,
    source: str,
    g_before: int,
    g_after: int,
    i_before: int,
    i_after: int,
    bed_type: str | None = None,
    actor: str | None = None,
    related_case_id: str | None = None,
    related_handoff_token_id: str | None = None,
    related_patient_id: str | None = None,
    note: str = "",
) -> HospitalSyncEvent:
    """Every write to live_bed_count/live_icu_count is audited through here —
    the shared half of `apply_bed_counts` (blind read-modify-write, used by the
    tiered syncs + QR-handoff admission/discharge) and the FR-18 walk-in
    functions below (atomic-guarded, so the two share one audit mechanism with
    two different concurrency shapes)."""
    event = HospitalSyncEvent(
        hospital_id=hospital.hospital_id,
        source=source,
        bed_type=bed_type,
        general_before=g_before,
        general_after=g_after,
        icu_before=i_before,
        icu_after=i_after,
        related_case_id=related_case_id,
        related_handoff_token_id=related_handoff_token_id,
        related_patient_id=related_patient_id,
        actor=actor,
        note=note,
    )
    db.add(event)
    db.flush()
    logger.info(
        "FR-16/18 sync hospital=%s source=%s general %s->%s icu %s->%s actor=%s case=%s handoff=%s patient=%s",
        hospital.hospital_id, source, g_before, g_after, i_before, i_after,
        actor, related_case_id, related_handoff_token_id, related_patient_id,
    )
    return event


def apply_bed_counts(
    db: Session,
    hospital: Hospital,
    *,
    general: int,
    icu: int,
    source: str,
    bed_type: str | None = None,
    actor: str | None = None,
    related_case_id: str | None = None,
    related_handoff_token_id: str | None = None,
    note: str = "",
) -> HospitalSyncEvent:
    """The single place bed counts are written. All tiers + the admission
    decrement call this, so the data always lands in `Hospital.bed_count_by_type`
    (== the FR-2 ranking inputs) and is always audited."""
    g_before, i_before = hospital.live_bed_count, hospital.live_icu_count
    hospital.live_bed_count = max(0, int(general))
    hospital.live_icu_count = max(0, int(icu))
    hospital.last_synced_at = _now()

    # The dashboard's fixed "total" (see Hospital.total_bed_count) only ever
    # ratchets UP, never down — a sync report of MORE free beds than we've
    # seen before means the hospital genuinely has that much capacity, so the
    # total must grow to match or "reserved" would go negative. A report of
    # FEWER beds (an admission, or a tier saying fewer are staffed right now)
    # never touches it — that's occupancy, not a capacity change.
    if hospital.live_bed_count > hospital.total_bed_count:
        hospital.total_bed_count = hospital.live_bed_count
    if hospital.live_icu_count > hospital.total_icu_bed_count:
        hospital.total_icu_bed_count = hospital.live_icu_count

    return _write_sync_event(
        db, hospital, source=source, bed_type=bed_type,
        g_before=g_before, g_after=hospital.live_bed_count,
        i_before=i_before, i_after=hospital.live_icu_count,
        actor=actor, related_case_id=related_case_id,
        related_handoff_token_id=related_handoff_token_id, note=note,
    )


def _get_hospital(db: Session, hospital_id: str) -> Hospital:
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise HospitalNotFound(f"hospital '{hospital_id}' does not exist")
    return hospital


def _require_tier(hospital: Hospital, tier: HospitalSyncTier) -> None:
    if hospital.hospital_sync_tier != tier:
        raise SyncTierMismatch(
            f"hospital {hospital.hospital_id} is on the "
            f"'{hospital.hospital_sync_tier.value}' tier, not '{tier.value}'"
        )


# --------------------------------------------------------------- shared helpers
def _coerce_counts(raw: dict) -> dict[str, int]:
    """Accept {'general','ICU'} in any case and coerce to non-negative ints."""
    lower = {str(k).lower(): v for k, v in raw.items()}
    if "general" not in lower or "icu" not in lower:
        raise ValueError(f"expected 'general' and 'ICU' keys, got {sorted(raw)}")
    return {"general": max(0, int(lower["general"])), "ICU": max(0, int(lower["icu"]))}


# --------------------------------------------------------------- tier 1: HMS API
# A real integration: when HMS_API_BASE_URL is set we GET
#   {base}/hospitals/{hospital_id}/beds  ->  {"general": N, "ICU": M}
# Otherwise fall back to a labelled mock feed (same degrade-to-stub pattern as
# app/services/maps.py). The mock is never presented as a live HMS reading.
_HMS_MOCK_FEED: dict[str, dict[str, int]] = {
    "HOSP-001": {"general": 9, "ICU": 3},
    "HOSP-005": {"general": 6, "ICU": 2},
    "HOSP-008": {"general": 5, "ICU": 5},
    "HOSP-009": {"general": 13, "ICU": 7},
}


def _fetch_hms_counts(hospital_id: str) -> tuple[dict[str, int], str]:
    """Return (counts, note). `note` records whether this was a live call or the mock."""
    settings = get_settings()
    base = settings.hms_api_base_url
    if base:
        url = f"{base.rstrip('/')}/hospitals/{hospital_id}/beds"
        headers = {"Authorization": f"Bearer {settings.hms_api_token}"} if settings.hms_api_token else {}
        try:
            resp = httpx.get(url, headers=headers, timeout=10.0)
            resp.raise_for_status()
            return _coerce_counts(resp.json()), f"live HMS API sync ({url})"
        except Exception as exc:  # noqa: BLE001 — never break the pipeline on an HMS failure
            logger.warning("HMS API call for %s failed: %s", hospital_id, exc)
            counts = dict(_HMS_MOCK_FEED.get(hospital_id, {"general": 5, "ICU": 2}))
            return counts, f"HMS API call failed ({exc}); used mock feed"
    counts = dict(_HMS_MOCK_FEED.get(hospital_id, {"general": 5, "ICU": 2}))
    return counts, "HMS_API_BASE_URL not set; used mock feed"


def sync_from_hms(db: Session, hospital_id: str) -> SyncOutcome:
    """Tier 1 — pull live bed counts from the hospital's HMS."""
    hospital = _get_hospital(db, hospital_id)
    _require_tier(hospital, HospitalSyncTier.hms_api)
    counts, note = _fetch_hms_counts(hospital_id)
    event = apply_bed_counts(
        db, hospital, general=counts["general"], icu=counts["ICU"],
        source="hms_api", actor="system", note=note,
    )
    db.commit()
    db.refresh(hospital)
    return SyncOutcome(hospital_id, "hms_api", hospital.bed_count_by_type,
                       hospital.last_synced_at, event)


# --------------------------------------------------------- tier 2: Google Sheets
# Real Google Sheet IDs are ~44 url-safe chars; require >=20 so obviously-fake
# demo URLs (…/d/abc/…) skip the network call and use the query-param parser.
_GSHEET_ID_RE = re.compile(r"docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,})")


def _fetch_sheet_counts(sheet_url: str) -> tuple[dict[str, int], str]:
    """Read bed counts from the hospital's Google Sheet.

    Real path: a `docs.google.com/spreadsheets/d/<id>` URL is fetched via the
    public CSV export and parsed as `label,count` rows (a `general` row and an
    `ICU` row, any case). Demo path: any other URL may carry `?general=&icu=`.
    Returns (counts, note)."""
    m = _GSHEET_ID_RE.search(sheet_url or "")
    if m:
        export = f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv"
        try:
            resp = httpx.get(export, timeout=10.0, follow_redirects=True)
            resp.raise_for_status()
            rows = {
                r[0].strip().lower(): r[1]
                for r in csv.reader(io.StringIO(resp.text))
                if len(r) >= 2 and r[0].strip()
            }
            return _coerce_counts({"general": rows["general"], "ICU": rows["icu"]}), (
                f"live Google Sheets sync ({export})"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google Sheets read failed for %s: %s", sheet_url, exc)
            # fall through to the query-param demo parser
    q = parse_qs(urlparse(sheet_url or "").query)
    counts = _coerce_counts(
        {"general": q.get("general", ["6"])[0], "ICU": q.get("icu", ["2"])[0]}
    )
    note = "demo Google Sheets sync (counts read from URL query)" if not m else (
        "Google Sheets export failed; used URL query fallback"
    )
    return counts, note


def sync_from_sheet(db: Session, hospital_id: str, sheet_url: str) -> SyncOutcome:
    """Tier 2 — read live bed counts from a Google Sheet the hospital maintains."""
    hospital = _get_hospital(db, hospital_id)
    _require_tier(hospital, HospitalSyncTier.google_sheets)
    if sheet_url:
        hospital.sheet_url = sheet_url
    url = hospital.sheet_url
    if not url:
        raise BadManualAdjust("no sheet_url configured for this hospital")
    counts, note = _fetch_sheet_counts(url)
    event = apply_bed_counts(
        db, hospital, general=counts["general"], icu=counts["ICU"],
        source="google_sheets", actor="system", note=note,
    )
    db.commit()
    db.refresh(hospital)
    return SyncOutcome(hospital_id, "google_sheets", hospital.bed_count_by_type,
                       hospital.last_synced_at, event)


# --------------------------------------------------------- tier 3: manual counter
def manual_adjust(
    db: Session, hospital_id: str, *, bed_type: str, delta: int, actor: str
) -> SyncOutcome:
    """Tier 3 — the hospital receptionist's one-tap ±1 counter."""
    hospital = _get_hospital(db, hospital_id)
    _require_tier(hospital, HospitalSyncTier.manual_counter)
    if delta not in (1, -1):
        raise BadManualAdjust("delta must be +1 or -1 (one tap)")
    if bed_type not in ("general", "ICU"):
        raise BadManualAdjust("bed_type must be 'general' or 'ICU'")

    general, icu = hospital.live_bed_count, hospital.live_icu_count
    if bed_type == "ICU":
        icu = max(0, icu + delta)
    else:
        general = max(0, general + delta)

    event = apply_bed_counts(
        db, hospital, general=general, icu=icu, source="manual_counter",
        bed_type=bed_type, actor=actor,
        note=f"manual one-tap {'+1' if delta > 0 else '-1'} on {bed_type} by {actor}",
    )
    db.commit()
    db.refresh(hospital)
    return SyncOutcome(hospital_id, "manual_counter", hospital.bed_count_by_type,
                       hospital.last_synced_at, event)


# ---------------------------------------------- (4) auto-decrement on admission
def record_admission_decrement(
    db: Session, *, case, handoff_token, admitted_by: str
) -> HospitalSyncEvent | None:
    """Decrement the admitting hospital's live bed count by 1, tied to THIS QR
    handoff. Called only from `handoff.scan()` on a valid, admission-confirming
    scan — never inferred from case status alone or from discharge.

    The now-fulfilled bed lock (a reservation) is released in the same step, so
    availability (`live_count − active_locks`) is unchanged at the instant of
    admission: a reserved bed simply becomes an occupied one.
    """
    from app.models.bed_lock import BedLock, LockStatus
    from app.services import bed_lock as bed_lock_svc

    lock = db.scalar(
        select(BedLock).where(
            BedLock.case_id == case.case_id, BedLock.lock_status == LockStatus.active
        )
    )
    if lock is not None:
        hospital_id = lock.hospital_id
        bed_type = lock.bed_type.value if hasattr(lock.bed_type, "value") else lock.bed_type
    elif case.selected_hospital_id is not None:
        hospital_id = case.selected_hospital_id
        bed_type = bed_lock_svc.bed_type_for_case(db, case).value
    else:
        logger.warning(
            "FR-16: admission of case %s has no hospital/bed lock — no decrement", case.case_id
        )
        return None

    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        logger.warning("FR-16: admission of case %s names unknown hospital %s", case.case_id, hospital_id)
        return None

    general, icu = hospital.live_bed_count, hospital.live_icu_count
    if bed_type == "ICU":
        icu = max(0, icu - 1)
    else:
        general = max(0, general - 1)

    event = apply_bed_counts(
        db, hospital, general=general, icu=icu, source="qr_handoff_admission",
        bed_type=bed_type, actor=admitted_by,
        related_case_id=case.case_id,
        related_handoff_token_id=handoff_token.token_id,
        note=(
            f"auto-decrement: QR handoff admission confirmed by {admitted_by} "
            f"(handoff token {handoff_token.token_id})"
        ),
    )
    if lock is not None:
        lock.lock_status = LockStatus.released
        lock.released_at = _now()
    return event


# ---------------------------------------------- (5) re-increment on discharge
def record_discharge_increment(db: Session, *, case) -> HospitalSyncEvent | None:
    """Give the bed back when a case is discharged (FR-8).

    Called ONLY from `feedback.trigger_discharge()`. This is the deliberate,
    audited counterpart to the admission decrement — tied to the explicit
    discharge event, written to `hospital_sync_events`, never inferred silently.
    Idempotent. The hospital's own sync tier remains authoritative and corrects
    this on its next sync (a discharged bed may still need turnover).
    """
    admit_ev = db.scalar(
        select(HospitalSyncEvent)
        .where(
            HospitalSyncEvent.related_case_id == case.case_id,
            HospitalSyncEvent.source == "qr_handoff_admission",
        )
        .order_by(HospitalSyncEvent.created_at.desc())
    )
    if admit_ev is None:
        return None  # never admitted via handoff -> nothing was decremented

    if db.scalar(
        select(HospitalSyncEvent).where(
            HospitalSyncEvent.related_case_id == case.case_id,
            HospitalSyncEvent.source == "discharge_bed_released",
        )
    ) is not None:
        return None  # already credited back

    hospital = db.get(Hospital, admit_ev.hospital_id)
    if hospital is None:
        return None

    bed_type = admit_ev.bed_type or "general"
    general, icu = hospital.live_bed_count, hospital.live_icu_count
    if bed_type == "ICU":
        icu += 1
    else:
        general += 1

    return apply_bed_counts(
        db, hospital, general=general, icu=icu, source="discharge_bed_released",
        bed_type=bed_type, actor="system:discharge", related_case_id=case.case_id,
        note=(
            f"bed released: case {case.case_id} discharged "
            f"(was admitted via handoff {admit_ev.related_handoff_token_id})"
        ),
    )


_WALKIN_COLUMN = {"general": "live_bed_count", "ICU": "live_icu_count"}


# ---------------------------------------------- (6) FR-18 walk-in admit/discharge
def record_walkin_admission_decrement(
    db: Session, *, hospital_id: str, bed_type: str, patient_id: str, actor: str
) -> HospitalSyncEvent:
    """Atomically decrement live_bed_count/live_icu_count for a walk-in/scheduled
    admission into a general/ICU bed (FR-18).

    The guard checks `live_count > active bed_locks of that type` — NOT just
    `live_count > 0` — because `live_bed_count` is the TOTAL physical capacity,
    and `bed_lock.acquire_lock()` reserves a slot against that total WITHOUT
    decrementing it (the decrement only happens later, at QR-handoff admission).
    A bare `> 0` guard would let a walk-in claim a bed a pending ambulance
    dispatch has already reserved — double-booking the same physical bed. This
    is exactly `bed_lock.acquire_lock`'s own capacity check, run from the other
    direction (subtracting a reservation from the total instead of adding one),
    as a single indivisible `UPDATE ... WHERE`. SQLite serialises the two
    statements on its write lock, so a walk-in admit and an ambulance's
    `acquire_lock()` can never both claim the last physical bed. On success this
    is the ONLY change needed for FR-2 ranking / FR-3 bed-lock to see the
    reduced availability — both already read live_bed_count/live_icu_count
    fresh at call time.
    """
    if bed_type not in _WALKIN_COLUMN:
        raise BadManualAdjust("bed_type must be 'general' or 'ICU'")
    hospital = _get_hospital(db, hospital_id)
    column = _WALKIN_COLUMN[bed_type]

    db.rollback()  # drop any read snapshot, mirror bed_lock.acquire_lock
    result = db.execute(
        text(
            f"""
            UPDATE hospitals SET {column} = {column} - 1
            WHERE hospital_id = :hid AND {column} > (
                SELECT COUNT(*) FROM bed_locks
                WHERE hospital_id = :hid AND bed_type = :bed_type AND lock_status = 'active'
            )
            """
        ),
        {"hid": hospital_id, "bed_type": bed_type},
    )
    if result.rowcount != 1:
        db.rollback()
        raise NoBedAvailable(f"no available {bed_type} bed at {hospital_id}")
    db.commit()
    db.refresh(hospital)

    after_general, after_icu = hospital.live_bed_count, hospital.live_icu_count
    before_general = after_general + 1 if bed_type == "general" else after_general
    before_icu = after_icu + 1 if bed_type == "ICU" else after_icu
    hospital.last_synced_at = _now()

    event = _write_sync_event(
        db, hospital, source="walkin_admission", bed_type=bed_type,
        g_before=before_general, g_after=after_general,
        i_before=before_icu, i_after=after_icu,
        actor=actor, related_patient_id=patient_id,
        note=f"walk-in admission of patient {patient_id} into a {bed_type} bed by {actor}",
    )
    db.commit()
    return event


def record_walkin_discharge_increment(
    db: Session, *, hospital_id: str, bed_type: str, patient_id: str, actor: str
) -> HospitalSyncEvent | None:
    """Credit a general/ICU bed back on a walk-in discharge (FR-18) — the
    counterpart to `record_walkin_admission_decrement`. Idempotent: refuses to
    double-credit a patient already discharged, mirroring
    `record_discharge_increment`'s idempotency check for the QR-handoff path.
    """
    if bed_type not in _WALKIN_COLUMN:
        raise BadManualAdjust("bed_type must be 'general' or 'ICU'")

    admit_ev = db.scalar(
        select(HospitalSyncEvent)
        .where(
            HospitalSyncEvent.related_patient_id == patient_id,
            HospitalSyncEvent.source == "walkin_admission",
        )
        .order_by(HospitalSyncEvent.created_at.desc())
    )
    if admit_ev is None:
        return None  # never admitted via this path -> nothing was decremented
    if db.scalar(
        select(HospitalSyncEvent).where(
            HospitalSyncEvent.related_patient_id == patient_id,
            HospitalSyncEvent.source == "walkin_discharge",
        )
    ) is not None:
        return None  # already credited back

    hospital = _get_hospital(db, hospital_id)
    column = _WALKIN_COLUMN[bed_type]

    db.rollback()
    db.execute(
        text(f"UPDATE hospitals SET {column} = {column} + 1 WHERE hospital_id = :hid"),
        {"hid": hospital_id},
    )
    db.commit()
    db.refresh(hospital)

    after_general, after_icu = hospital.live_bed_count, hospital.live_icu_count
    before_general = after_general - 1 if bed_type == "general" else after_general
    before_icu = after_icu - 1 if bed_type == "ICU" else after_icu
    hospital.last_synced_at = _now()

    event = _write_sync_event(
        db, hospital, source="walkin_discharge", bed_type=bed_type,
        g_before=before_general, g_after=after_general,
        i_before=before_icu, i_after=after_icu,
        actor=actor, related_patient_id=patient_id,
        note=f"bed released: walk-in patient {patient_id} discharged",
    )
    db.commit()
    return event


# --------------------------------------------------------------- reads
def recent_events(db: Session, hospital_id: str, limit: int = 20) -> list[HospitalSyncEvent]:
    return list(
        db.scalars(
            select(HospitalSyncEvent)
            .where(HospitalSyncEvent.hospital_id == hospital_id)
            .order_by(HospitalSyncEvent.created_at.desc())
            .limit(limit)
        )
    )
