"""FR-5 endpoints: blood check, blood-bank holds + coordinator decisions."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.blood import BloodBankHold
from app.models.case import Case
from app.schemas.blood import (
    BloodBankHoldOut,
    BloodBankOut,
    BloodCheckOut,
    HoldDecisionRequest,
)
from app.services import blood as svc
from app.services.access import require_blood_bank_scope
from app.services.auth_deps import get_principal, require_role
from app.services.security import Principal

router = APIRouter(tags=["blood"])


def _require_case(case_id: str, db: Session) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    return case


@router.get("/blood-banks", response_model=list[BloodBankOut])
def list_blood_banks(
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db)
) -> list[BloodBankOut]:
    """A coordinator sees only their own blood bank (FR-11)."""
    rows = svc.list_blood_banks(db)
    if principal.role == Role.blood_bank_coordinator and not principal.is_privileged:
        rows = [b for b in rows if b.blood_bank_id == principal.blood_bank_id]
    return rows


@router.get("/blood-banks/{blood_bank_id}/holds", response_model=list[BloodBankHoldOut])
def blood_bank_holds(
    blood_bank_id: str,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(get_db),
) -> list[BloodBankHoldOut]:
    """The coordinator's dashboard: hold requests waiting on this blood bank."""
    require_blood_bank_scope(principal, blood_bank_id)
    return svc.list_holds(db, blood_bank_id)


@router.get(
    "/blood-bank-holds",
    response_model=list[BloodBankHoldOut],
    dependencies=[Depends(require_role(Role.admin, Role.control_room))],
)
def all_blood_bank_holds(db: Session = Depends(get_db)) -> list[BloodBankHoldOut]:
    """Admin/control_room view: every hold request across every blood bank.

    A coordinator is scoped to their own bank (see blood_bank_holds above);
    admin has no blood_bank_id of its own, so it needs this unscoped view
    rather than being unable to see holds at all.
    """
    return svc.list_holds(db, blood_bank_id=None)


@router.get("/cases/{case_id}/blood-check", response_model=BloodCheckOut)
def get_blood_check(case_id: str, db: Session = Depends(get_db)) -> BloodCheckOut:
    _require_case(case_id, db)
    check = svc.get_blood_check(db, case_id)
    if check is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "no blood check for this case — its symptoms don't suggest a blood requirement",
        )
    return check


@router.get("/cases/{case_id}/blood-bank-hold", response_model=BloodBankHoldOut)
def get_case_hold(case_id: str, db: Session = Depends(get_db)) -> BloodBankHoldOut:
    _require_case(case_id, db)
    hold = svc.get_hold_for_case(db, case_id)
    if hold is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no blood-bank hold for this case")
    return hold


def _decide(hold_id: str, confirm: bool, coordinator_id: str, principal: Principal, db: Session):
    hold = db.get(BloodBankHold, hold_id)
    if hold is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "hold not found")
    require_blood_bank_scope(principal, hold.blood_bank_id)
    try:
        return svc.decide_hold(db, hold_id, confirm=confirm, decided_by=coordinator_id)
    except svc.HoldDecisionError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))


@router.post("/blood-bank-holds/{hold_id}/confirm", response_model=BloodBankHoldOut)
def confirm_hold(
    hold_id: str, payload: HoldDecisionRequest,
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
) -> BloodBankHoldOut:
    return _decide(hold_id, True, payload.coordinator_id, principal, db)


@router.post("/blood-bank-holds/{hold_id}/reject", response_model=BloodBankHoldOut)
def reject_hold(
    hold_id: str, payload: HoldDecisionRequest,
    principal: Principal = Depends(get_principal), db: Session = Depends(get_db),
) -> BloodBankHoldOut:
    return _decide(hold_id, False, payload.coordinator_id, principal, db)
