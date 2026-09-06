"""FR-20 Staff Attendance / Clock-in-out."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hospital_staff import HospitalStaffMember, OnDutyStatus
from app.models.staff_attendance import StaffAttendance
from app.services import hospital_staff as staff_svc


class StaffNotFound(Exception):
    pass


class AlreadyClockedIn(Exception):
    pass


class NotClockedIn(Exception):
    pass


def get_open_attendance(db: Session, staff_id: str) -> StaffAttendance | None:
    return db.scalar(
        select(StaffAttendance).where(
            StaffAttendance.staff_id == staff_id, StaffAttendance.clock_out_at.is_(None)
        )
    )


def clock_in(
    db: Session, staff_id: str, *, actor: str, shift_label: str | None = None, notes: str | None = None
) -> StaffAttendance:
    staff = db.get(HospitalStaffMember, staff_id)
    if staff is None:
        raise StaffNotFound(f"staff '{staff_id}' does not exist")
    if get_open_attendance(db, staff_id) is not None:
        raise AlreadyClockedIn(f"staff '{staff_id}' is already clocked in")

    attendance = StaffAttendance(
        staff_id=staff_id, hospital_id=staff.hospital_id,
        shift_label=shift_label, recorded_by=actor, notes=notes,
    )
    db.add(attendance)
    # set_on_duty_status commits — persists the attendance row staged above too
    # (a commit never discards other pending changes on the session, only a
    # rollback does; see the FR-18 hospital_sync note for the case that DOES
    # matter, which doesn't apply to this plain read-modify-write helper).
    staff_svc.set_on_duty_status(db, staff_id, OnDutyStatus.on_duty)
    db.refresh(attendance)
    return attendance


def clock_out(db: Session, staff_id: str, *, actor: str) -> StaffAttendance:
    if db.get(HospitalStaffMember, staff_id) is None:
        raise StaffNotFound(f"staff '{staff_id}' does not exist")
    attendance = get_open_attendance(db, staff_id)
    if attendance is None:
        raise NotClockedIn(f"staff '{staff_id}' is not currently clocked in")

    attendance.clock_out_at = datetime.now(timezone.utc)
    staff_svc.set_on_duty_status(db, staff_id, OnDutyStatus.off_duty)  # commits both changes
    db.refresh(attendance)
    return attendance


def history_for_staff(db: Session, staff_id: str) -> list[StaffAttendance]:
    return list(
        db.scalars(
            select(StaffAttendance)
            .where(StaffAttendance.staff_id == staff_id)
            .order_by(StaffAttendance.clock_in_at.desc())
        )
    )


def history_for_hospital(db: Session, hospital_id: str) -> list[StaffAttendance]:
    return list(
        db.scalars(
            select(StaffAttendance)
            .where(StaffAttendance.hospital_id == hospital_id)
            .order_by(StaffAttendance.clock_in_at.desc())
        )
    )
