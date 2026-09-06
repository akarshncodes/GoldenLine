"""FR-7: derive the transit timeline from timestamps already stored across FR-0..FR-6.

Nothing new is persisted — this walks the existing rows and returns a sorted list
of {event, at, detail} entries.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.bed_lock import BedLock
from app.models.blood import BloodBankHold, BloodCheck
from app.models.case import Case
from app.models.hospital import Hospital
from app.models.prep import PrepAction, PrepActionStatus
from app.models.route import CaseRoute, TrafficAlert, WaypointSuggestion


@dataclass
class TimelineEvent:
    event: str
    at: datetime
    detail: str | None = None


def build_transit_timeline(db: Session, case: Case) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []

    def add(event: str, at: datetime | None, detail: str | None = None) -> None:
        if at is None:
            return
        # Rows written by raw SQL come back tz-aware, ORM rows come back naive —
        # normalise to naive UTC so a single sorted list is possible.
        if at.tzinfo is not None:
            at = at.astimezone(timezone.utc).replace(tzinfo=None)
        events.append(TimelineEvent(event=event, at=at, detail=detail))

    add("case_created", case.created_at, f"path {case.creation_path.value}")
    add("sos_triggered", case.sos_trigger_timestamp, "family phone GPS (ambulance search only)")
    if case.gps_source == "helper_device":
        add("helper_location_reported", case.gps_timestamp)

    assessment = db.scalar(select(Assessment).where(Assessment.case_id == case.case_id))
    if assessment is not None:
        add(
            "symptoms_logged",
            assessment.created_at,
            f"{assessment.criticality_level.value}; {', '.join(assessment.symptom_checklist)}",
        )

    if case.selection_timestamp is not None:
        hospital = db.get(Hospital, case.selected_hospital_id)
        name = hospital.name if hospital else case.selected_hospital_id
        add("hospital_selected", case.selection_timestamp, f"{name} ({case.selected_via})")

    for lock in db.scalars(select(BedLock).where(BedLock.case_id == case.case_id)):
        add("bed_locked", lock.locked_at, f"{lock.bed_type.value} bed")
        add("bed_lock_released", lock.released_at, f"{lock.bed_type.value} bed")

    route = db.scalar(select(CaseRoute).where(CaseRoute.case_id == case.case_id))
    if route is not None:
        add(
            "route_computed",
            route.created_at,
            f"ETA {route.eta_min_minutes}-{route.eta_max_minutes} min ({route.route_source})",
        )
    alert = db.scalar(select(TrafficAlert).where(TrafficAlert.case_id == case.case_id))
    if alert is not None:
        add("traffic_alert_sent", alert.traffic_alert_sent_at)

    ws = db.scalar(select(WaypointSuggestion).where(WaypointSuggestion.case_id == case.case_id))
    if ws is not None:
        add("waypoint_suggested", ws.suggested_at)
        add(f"waypoint_{ws.status.value}", ws.decided_at)

    bc = db.scalar(select(BloodCheck).where(BloodCheck.case_id == case.case_id))
    if bc is not None:
        add("blood_check_run", bc.checked_at, bc.outcome.value)
    for hold in db.scalars(select(BloodBankHold).where(BloodBankHold.case_id == case.case_id)):
        add("blood_bank_hold_requested", hold.requested_at)
        add(f"blood_bank_hold_{hold.hold_status.value}", hold.decided_at)

    for pa in db.scalars(select(PrepAction).where(PrepAction.case_id == case.case_id)):
        if pa.status == PrepActionStatus.confirmed:
            add("prep_action_confirmed", pa.confirmed_at, pa.action_key)

    add("qr_handoff_scanned", case.admitted_at, case.admitted_by)
    add("discharged", case.discharged_at)

    events.sort(key=lambda e: e.at)
    return events
