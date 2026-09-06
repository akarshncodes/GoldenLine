"""FR-19 Doctor/Staff Roster + On-Duty Status."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.models.hospital_staff import HospitalStaffMember, OnDutyStatus, StaffCategory


class HospitalNotFound(Exception):
    pass


class StaffNotFound(Exception):
    pass


def create_staff(
    db: Session,
    *,
    hospital_id: str,
    full_name: str,
    staff_category: StaffCategory,
    specialty: str | None = None,
    phone_number: str | None = None,
    created_by: str | None = None,
) -> HospitalStaffMember:
    if db.get(Hospital, hospital_id) is None:
        raise HospitalNotFound(f"hospital '{hospital_id}' does not exist")
    staff = HospitalStaffMember(
        hospital_id=hospital_id,
        full_name=full_name,
        staff_category=staff_category,
        specialty=specialty,
        phone_number=phone_number,
        created_by=created_by,
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


def list_for_hospital(db: Session, hospital_id: str, *, include_inactive: bool = False) -> list[HospitalStaffMember]:
    stmt = select(HospitalStaffMember).where(HospitalStaffMember.hospital_id == hospital_id)
    if not include_inactive:
        stmt = stmt.where(HospitalStaffMember.is_active.is_(True))
    return list(db.scalars(stmt.order_by(HospitalStaffMember.full_name)))


def list_all(db: Session, *, include_inactive: bool = False) -> list[HospitalStaffMember]:
    stmt = select(HospitalStaffMember)
    if not include_inactive:
        stmt = stmt.where(HospitalStaffMember.is_active.is_(True))
    return list(db.scalars(stmt.order_by(HospitalStaffMember.hospital_id, HospitalStaffMember.full_name)))


def get(db: Session, staff_id: str) -> HospitalStaffMember | None:
    return db.get(HospitalStaffMember, staff_id)


def set_on_duty_status(db: Session, staff_id: str, status: OnDutyStatus) -> HospitalStaffMember:
    staff = db.get(HospitalStaffMember, staff_id)
    if staff is None:
        raise StaffNotFound(f"staff '{staff_id}' does not exist")
    staff.on_duty_status = status
    db.commit()
    db.refresh(staff)
    return staff


def deactivate(db: Session, staff_id: str) -> HospitalStaffMember:
    """Soft delete: is_active=False, on_duty flipped off. Historical attendance
    rows (FR-20) keep referencing this staff_id — nothing is hard-deleted."""
    staff = db.get(HospitalStaffMember, staff_id)
    if staff is None:
        raise StaffNotFound(f"staff '{staff_id}' does not exist")
    staff.is_active = False
    staff.on_duty_status = OnDutyStatus.off_duty
    db.commit()
    db.refresh(staff)
    return staff
