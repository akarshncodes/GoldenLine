"""Admin-only demo reset — not a formal FRP requirement, added so a live demo
can restart clean without a backend restart.

Wipes every case-lifecycle table and restores hospitals'/blood banks' live
counters to their seeded values. Static rosters (users, and the hospital /
blood-bank / waypoint rows themselves) are left untouched.
"""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.auth import (
    DeletionRequest,
    DuplicateMergeLog,
    OtpVerification,
    PasswordResetToken,
    RateLimitFlag,
)
from app.models.bed_lock import BedLock, ConflictLog
from app.models.blood import BloodBank, BloodBankHold, BloodCheck
from app.models.case import Case
from app.models.control_room import Flag
from app.models.feedback import CaseFeedback, FeedbackInvite
from app.models.handoff import QrHandoffToken
from app.models.hospital import Hospital
from app.models.hospital_bed_report import HospitalBedReport
from app.models.hospital_sync import HospitalSyncEvent
from app.models.patient import BedAssignment, Patient
from app.models.prep import PrepAction
from app.models.route import CaseRoute, TrafficAlert, WaypointSuggestion
from app.models.sms import SmsMessage
from app.models.tracking import CaseTrackingToken
from app.services.hospital_seed import SEED_HOSPITALS
from app.services.hospital_sync import SEED_SYNC_TIERS
from app.services.reference_seed import SEED_BLOOD_BANKS

# Every one of these has a foreign key to cases.case_id — must be cleared
# before the cases themselves.
_CASE_CHILD_TABLES = [
    Assessment,
    BedLock,
    ConflictLog,
    BloodCheck,
    BloodBankHold,
    DeletionRequest,
    DuplicateMergeLog,
    CaseFeedback,
    FeedbackInvite,
    QrHandoffToken,
    PrepAction,
    CaseRoute,
    TrafficAlert,
    WaypointSuggestion,
    CaseTrackingToken,
]

# Standalone event/log tables — no FK to cases, just demo noise to clear.
_STANDALONE_TABLES = [
    OtpVerification,
    PasswordResetToken,
    RateLimitFlag,
    Flag,
    HospitalSyncEvent,
    HospitalBedReport,
    SmsMessage,
]


def reset_demo_data(db: Session) -> dict:
    for model in _CASE_CHILD_TABLES:
        db.execute(delete(model))
    db.execute(delete(Case))
    for model in _STANDALONE_TABLES:
        db.execute(delete(model))

    # FR-18 patient census: every row here is either linked to a case just
    # deleted above (emergency_case) or a walk-in admission that decremented
    # a hospital's live bed count — since that count is about to be reset to
    # full below, leaving these rows behind would make the census screen show
    # "admitted" patients for beds the dashboard now claims are all free.
    # Deliberately NOT clearing hospital_staff/hospital_inventory_items here —
    # those don't depend on case/bed state, so they never go stale.
    db.execute(delete(BedAssignment))
    db.execute(delete(Patient))

    hospitals_reset = 0
    seed_hospitals_by_id = {h["hospital_id"]: h for h in SEED_HOSPITALS}
    for hospital in db.query(Hospital).all():
        seed = seed_hospitals_by_id.get(hospital.hospital_id)
        if seed is None:
            continue
        hospital.live_bed_count = seed["live_bed_count"]
        hospital.live_icu_count = seed["live_icu_count"]
        hospital.total_bed_count = seed["total_bed_count"]
        hospital.total_icu_bed_count = seed["total_icu_bed_count"]
        hospital.blood_stock_by_group = dict(seed["blood_stock_by_group"])
        hospital.hospital_sync_tier = SEED_SYNC_TIERS.get(
            hospital.hospital_id, hospital.hospital_sync_tier
        )
        hospital.last_synced_at = None
        hospitals_reset += 1

    blood_banks_reset = 0
    seed_banks_by_id = {b["blood_bank_id"]: b for b in SEED_BLOOD_BANKS}
    for bank in db.query(BloodBank).all():
        seed = seed_banks_by_id.get(bank.blood_bank_id)
        if seed is None:
            continue
        bank.stock_by_group = dict(seed["stock_by_group"])
        blood_banks_reset += 1

    db.commit()
    return {
        "reset": True,
        "hospitals_reset": hospitals_reset,
        "blood_banks_reset": blood_banks_reset,
    }
