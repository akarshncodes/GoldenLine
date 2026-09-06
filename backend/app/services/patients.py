"""FR-18 Patient Census + manual admit/discharge/bed-assignment.

Independent of the emergency case pipeline (FR-0..FR-16) — but every case
admitted via a QR handoff also gets a visibility-only entry here
(`patient_type='emergency_case'`), created/discharged by the hooks at the
bottom of this file, so the census reflects EVERY patient in the hospital.
Walk-in/scheduled admissions into a general/ICU bed atomically decrement the
SAME `Hospital.live_bed_count`/`live_icu_count` columns FR-2 ranking and FR-3
bed-lock read from (via `hospital_sync.record_walkin_admission_decrement`), so
neither of those needs any change to see the reduced availability.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case import Case, Gender
from app.models.hospital import Hospital
from app.models.patient import BedAssignment, BedAssignmentStatus, Patient, PatientStatus, PatientType
from app.services import hospital_sync

_EMERGENCY_BED_TYPES = {"general", "ICU"}


class HospitalNotFound(Exception):
    pass


class PatientNotFound(Exception):
    pass


class InvalidPatientState(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_patient(
    db: Session,
    *,
    hospital_id: str,
    full_name: str,
    approx_age: int | None = None,
    gender: Gender | None = None,
    phone_number: str | None = None,
    patient_type: PatientType = PatientType.walk_in,
    created_by: str | None = None,
) -> Patient:
    if db.get(Hospital, hospital_id) is None:
        raise HospitalNotFound(f"hospital '{hospital_id}' does not exist")
    patient = Patient(
        hospital_id=hospital_id,
        full_name=full_name,
        approx_age=approx_age,
        gender=gender,
        phone_number=phone_number,
        patient_type=patient_type,
        status=PatientStatus.waiting,
        created_by=created_by,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def list_for_hospital(db: Session, hospital_id: str, status: PatientStatus | None = None) -> list[Patient]:
    stmt = select(Patient).where(Patient.hospital_id == hospital_id)
    if status is not None:
        stmt = stmt.where(Patient.status == status)
    return list(db.scalars(stmt.order_by(Patient.created_at.desc())))


def list_all(db: Session) -> list[Patient]:
    return list(db.scalars(select(Patient).order_by(Patient.created_at.desc())))


def get(db: Session, patient_id: str) -> Patient | None:
    return db.get(Patient, patient_id)


def get_active_assignment(db: Session, patient_id: str) -> BedAssignment | None:
    return db.scalar(
        select(BedAssignment).where(
            BedAssignment.patient_id == patient_id, BedAssignment.status == BedAssignmentStatus.active
        )
    )


def admit(db: Session, patient_id: str, *, category_code: str, bed_label: str | None, actor: str) -> BedAssignment:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise PatientNotFound(f"patient '{patient_id}' does not exist")
    if patient.status == PatientStatus.admitted:
        raise InvalidPatientState("patient is already admitted")
    if patient.status in (PatientStatus.discharged, PatientStatus.cancelled):
        raise InvalidPatientState(f"patient is {patient.status.value}, cannot admit")

    # Only general/ICU interact with the emergency pipeline's shared capacity
    # columns; any other (FR-17) category is purely local bookkeeping.
    #
    # This call must happen BEFORE any other ORM mutation in this function:
    # record_walkin_admission_decrement calls db.rollback() internally (to drop
    # any stale read snapshot ahead of its own atomic UPDATE, same as
    # bed_lock.acquire_lock) which would silently discard any uncommitted
    # changes already staged on this session.
    if category_code in _EMERGENCY_BED_TYPES:
        hospital_sync.record_walkin_admission_decrement(
            db, hospital_id=patient.hospital_id, bed_type=category_code,
            patient_id=patient.patient_id, actor=actor,
        )
        patient = db.get(Patient, patient_id)  # re-fetch: rollback above expired it

    assignment = BedAssignment(
        patient_id=patient.patient_id,
        hospital_id=patient.hospital_id,
        category_code=category_code,
        bed_label=bed_label,
        assigned_by=actor,
    )
    db.add(assignment)
    patient.status = PatientStatus.admitted
    db.commit()
    db.refresh(assignment)
    return assignment


def discharge(db: Session, patient_id: str, *, actor: str) -> BedAssignment:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise PatientNotFound(f"patient '{patient_id}' does not exist")
    assignment = get_active_assignment(db, patient_id)
    if assignment is None:
        raise InvalidPatientState("patient has no active bed assignment")

    # Same ordering rule as admit() above: call this BEFORE mutating
    # assignment/patient, since its internal db.rollback() would otherwise wipe
    # out those uncommitted changes.
    category_code = assignment.category_code
    if category_code in _EMERGENCY_BED_TYPES:
        hospital_sync.record_walkin_discharge_increment(
            db, hospital_id=patient.hospital_id, bed_type=category_code,
            patient_id=patient.patient_id, actor=actor,
        )
        assignment = db.get(BedAssignment, assignment.bed_assignment_id)  # re-fetch
        patient = db.get(Patient, patient_id)

    assignment.status = BedAssignmentStatus.released
    assignment.released_at = _utcnow()
    assignment.released_by = actor
    patient.status = PatientStatus.discharged

    db.commit()
    db.refresh(assignment)
    return assignment


# ----------------------------- emergency-pipeline census hooks (visibility-only) ---
def create_census_entry_for_case_admission(db: Session, *, case: Case, handoff_token) -> Patient | None:
    """Called from `handoff.scan()` on a confirmed QR-handoff admission.

    Visibility-only: `hospital_sync.record_admission_decrement()` already
    decremented the hospital's live count for the locked bed type, so this does
    NOT decrement again — it only makes the case's patient show up in the
    hospital-wide census. Idempotent (a repeated scan is a no-op here too, same
    as the case-status guard in handoff.scan() itself). Does not commit — the
    caller (handoff.scan()) commits the whole transaction.
    """
    if case.selected_hospital_id is None:
        return None
    existing = db.scalar(select(Patient).where(Patient.linked_case_id == case.case_id))
    if existing is not None:
        return existing

    from app.services import bed_lock as bed_lock_svc

    bed_type = bed_lock_svc.bed_type_for_case(db, case).value
    patient = Patient(
        hospital_id=case.selected_hospital_id,
        full_name=case.patient_name or "Unknown (emergency case)",
        approx_age=case.patient_approx_age,
        gender=case.patient_gender,
        patient_type=PatientType.emergency_case,
        linked_case_id=case.case_id,
        status=PatientStatus.admitted,
        created_by="system:qr_handoff",
    )
    db.add(patient)
    db.flush()
    db.add(BedAssignment(
        patient_id=patient.patient_id,
        hospital_id=case.selected_hospital_id,
        category_code=bed_type,
        assigned_by="system:qr_handoff",
    ))
    return patient


def discharge_census_entry_for_case(db: Session, *, case: Case) -> None:
    """Called from `feedback.trigger_discharge()`. Visibility-only — the bed was
    already credited back via `record_discharge_increment()`. Idempotent. Does
    not commit — the caller commits the whole transaction.
    """
    patient = db.scalar(select(Patient).where(Patient.linked_case_id == case.case_id))
    if patient is None or patient.status == PatientStatus.discharged:
        return
    assignment = get_active_assignment(db, patient.patient_id)
    if assignment is not None:
        assignment.status = BedAssignmentStatus.released
        assignment.released_at = _utcnow()
        assignment.released_by = "system:discharge"
    patient.status = PatientStatus.discharged
