"""FR-12: Path A duplicate-request auto-merge (location proximity + time window)."""
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DUPLICATE_MERGE_RADIUS_METERS, DUPLICATE_MERGE_WINDOW_MINUTES
from app.models.auth import DuplicateMergeLog
from app.models.case import Case, CaseStatus, CreationPath


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _metres_between(lat1, lon1, lat2, lon2) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def find_mergeable_path_a_case(
    db: Session, *, latitude: float, longitude: float
) -> tuple[Case, float, int] | None:
    """Return (existing_case, distance_m, seconds_apart) if a recent nearby Path A
    SOS exists — BOTH proximity AND time window must hold."""
    now = _utcnow()
    cutoff = now - timedelta(minutes=DUPLICATE_MERGE_WINDOW_MINUTES)

    recent = db.scalars(
        select(Case).where(
            Case.creation_path == CreationPath.A,
            Case.created_at >= cutoff,
            Case.status.notin_([CaseStatus.DISCHARGED]),
            Case.sos_trigger_latitude.is_not(None),
        )
    )
    for case in recent:
        dist = _metres_between(
            latitude, longitude, case.sos_trigger_latitude, case.sos_trigger_longitude
        )
        if dist <= DUPLICATE_MERGE_RADIUS_METERS:
            created = case.created_at
            if created.tzinfo is not None:
                created = created.astimezone(timezone.utc).replace(tzinfo=None)
            return case, round(dist, 1), int((now - created).total_seconds())
    return None


def log_merge(
    db: Session, *, primary_case: Case, duplicate_source: str | None,
    latitude: float, longitude: float, distance_m: float, seconds_apart: int,
) -> DuplicateMergeLog:
    row = DuplicateMergeLog(
        primary_case_id=primary_case.case_id,
        duplicate_source=duplicate_source,
        reason=(
            f"Near-duplicate SOS {distance_m} m away, {seconds_apart}s after the "
            f"first — within {DUPLICATE_MERGE_RADIUS_METERS} m / "
            f"{DUPLICATE_MERGE_WINDOW_MINUTES} min. Merged into the existing case."
        ),
        latitude=latitude,
        longitude=longitude,
        distance_metres=distance_m,
        seconds_apart=seconds_apart,
    )
    db.add(row)
    db.flush()
    return row
