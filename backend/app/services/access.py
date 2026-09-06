"""FR-11 role-based scoping helpers used by the endpoint dependencies."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import Role
from app.models.blood import BloodBankHold
from app.models.case import Case
from app.services.security import Principal

_FORBIDDEN = HTTPException(status.HTTP_403_FORBIDDEN, "not authorised for this resource")


def can_see_case(db: Session, principal: Principal, case: Case) -> bool:
    if principal.is_privileged:  # admin, control_room
        return True

    role = principal.role
    if role == Role.family:
        return case.family_user_id == principal.user_id
    if role == Role.helper:
        return case.helper_id == principal.user_id
    if role == Role.hospital_receptionist:
        return (
            case.selected_hospital_id is not None
            and case.selected_hospital_id == principal.hospital_id
        )
    if role == Role.blood_bank_coordinator:
        return db.scalar(
            select(BloodBankHold.blood_bank_hold_id).where(
                BloodBankHold.case_id == case.case_id,
                BloodBankHold.blood_bank_id == principal.blood_bank_id,
            )
        ) is not None
    return False


def require_case_access(db: Session, principal: Principal, case: Case) -> Case:
    if not can_see_case(db, principal, case):
        raise _FORBIDDEN
    return case


def require_roles(principal: Principal, *roles: Role) -> None:
    if principal.role not in roles and not principal.is_privileged:
        raise _FORBIDDEN


def require_hospital_scope(principal: Principal, hospital_id: str) -> None:
    if principal.is_privileged:
        return
    if principal.role == Role.hospital_receptionist and principal.hospital_id == hospital_id:
        return
    raise _FORBIDDEN


def require_blood_bank_scope(principal: Principal, blood_bank_id: str) -> None:
    if principal.is_privileged:
        return
    if principal.role == Role.blood_bank_coordinator and principal.blood_bank_id == blood_bank_id:
        return
    raise _FORBIDDEN
