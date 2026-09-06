"""FR-18 endpoints: hospital-wide patient census + manual admit/discharge/bed-assignment."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.patient import Patient, PatientStatus, PatientType
from app.schemas.patient import AdmitRequest, BedAssignmentOut, PatientCreateRequest, PatientOut
from app.services import hospital_sync
from app.services import patients as svc
from app.services.access import require_hospital_scope
from app.services.auth_deps import get_principal, require_role
from app.services.security import Principal

router = APIRouter(tags=["patients"])


def _require_patient(patient_id: str, db: Session) -> Patient:
    patient = svc.get(db, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"patient '{patient_id}' does not exist")
    return patient


@router.post("/hospitals/{hospital_id}/patients", response_model=PatientOut)
def create_patient(
    hospital_id: str,
    payload: PatientCreateRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> PatientOut:
    require_hospital_scope(principal, hospital_id)
    try:
        return svc.create_patient(
            db,
            hospital_id=hospital_id,
            full_name=payload.full_name,
            approx_age=payload.approx_age,
            gender=payload.gender,
            phone_number=payload.phone_number,
            patient_type=PatientType(payload.patient_type),
            created_by=principal.user_id,
        )
    except svc.HospitalNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get("/hospitals/{hospital_id}/patients", response_model=list[PatientOut])
def list_hospital_patients(
    hospital_id: str,
    patient_status: PatientStatus | None = Query(default=None, alias="status"),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[PatientOut]:
    require_hospital_scope(principal, hospital_id)
    return svc.list_for_hospital(db, hospital_id, status=patient_status)


@router.get(
    "/patients",
    response_model=list[PatientOut],
    dependencies=[Depends(require_role(Role.admin, Role.control_room))],
)
def all_patients(db: Session = Depends(get_db)) -> list[PatientOut]:
    """Admin/control_room unscoped view across every hospital (mirrors /bed-categories)."""
    return svc.list_all(db)


@router.get("/patients/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> PatientOut:
    patient = _require_patient(patient_id, db)
    require_hospital_scope(principal, patient.hospital_id)
    return patient


@router.post("/patients/{patient_id}/admit", response_model=BedAssignmentOut)
def admit_patient(
    patient_id: str,
    payload: AdmitRequest,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> BedAssignmentOut:
    patient = _require_patient(patient_id, db)
    require_hospital_scope(principal, patient.hospital_id)
    try:
        return svc.admit(
            db, patient_id, category_code=payload.category_code,
            bed_label=payload.bed_label, actor=principal.user_id,
        )
    except svc.InvalidPatientState as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    except hospital_sync.NoBedAvailable as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post("/patients/{patient_id}/discharge", response_model=BedAssignmentOut)
def discharge_patient(
    patient_id: str, principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> BedAssignmentOut:
    patient = _require_patient(patient_id, db)
    require_hospital_scope(principal, patient.hospital_id)
    try:
        return svc.discharge(db, patient_id, actor=principal.user_id)
    except svc.InvalidPatientState as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
