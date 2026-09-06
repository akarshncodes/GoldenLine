"""FR-5 orchestration: conditional blood check + blood-bank hold request."""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BLOOD_UNITS_PER_CASE, UNIVERSAL_DONOR_GROUP
from app.models.assessment import Assessment
from app.models.blood import (
    BloodBank,
    BloodBankHold,
    BloodCheck,
    BloodCheckOutcome,
    HoldStatus,
)
from app.models.case import Case
from app.models.hospital import Hospital

# FR-5 item 1: only run when these symptom flags are present.
BLOOD_REQUIREMENT_SYMPTOMS = {"visible_bleeding", "trauma"}


class HoldDecisionError(Exception):
    pass


def blood_requirement_symptoms(symptom_checklist: list[str]) -> list[str]:
    return sorted(BLOOD_REQUIREMENT_SYMPTOMS.intersection(symptom_checklist))


def get_blood_check(db: Session, case_id: str) -> BloodCheck | None:
    return db.scalar(select(BloodCheck).where(BloodCheck.case_id == case_id))


def get_hold_for_case(db: Session, case_id: str) -> BloodBankHold | None:
    return db.scalar(select(BloodBankHold).where(BloodBankHold.case_id == case_id))


def _hospital_stock_sufficient(stock: dict, blood_group: str | None) -> bool:
    group = blood_group or UNIVERSAL_DONOR_GROUP
    return int(stock.get(group, 0)) >= BLOOD_UNITS_PER_CASE


def _linked_blood_bank(db: Session, hospital_id: str) -> BloodBank | None:
    for bank in db.scalars(select(BloodBank)):
        if hospital_id in (bank.linked_hospital_ids or []):
            return bank
    return None


def run_for_case(db: Session, case: Case, *, blood_group: str | None = None) -> BloodCheck | None:
    """Run only if the symptoms suggest a blood requirement. Returns None otherwise."""
    if get_blood_check(db, case.case_id) is not None:
        return get_blood_check(db, case.case_id)

    assessment = db.scalar(select(Assessment).where(Assessment.case_id == case.case_id))
    symptoms = list(assessment.symptom_checklist) if assessment else []
    triggers = blood_requirement_symptoms(symptoms)
    if not triggers:
        return None  # FR-5 item 1 — not relevant, do not create noise

    hospital = db.get(Hospital, case.selected_hospital_id)
    stock = dict(hospital.blood_stock_by_group or {}) if hospital else {}
    sufficient = _hospital_stock_sufficient(stock, blood_group)

    outcome = (
        BloodCheckOutcome.hospital_stock_ok
        if sufficient
        else BloodCheckOutcome.blood_bank_hold_requested
    )
    check = BloodCheck(
        case_id=case.case_id,
        hospital_id=case.selected_hospital_id,
        blood_requirement_flag=True,
        blood_group=blood_group,
        triggered_by_symptoms=triggers,
        hospital_stock_sufficient=sufficient,
        hospital_stock_snapshot=stock,
        outcome=outcome,
    )
    db.add(check)

    if not sufficient:
        bank = _linked_blood_bank(db, case.selected_hospital_id)
        if bank is not None:
            db.add(
                BloodBankHold(
                    case_id=case.case_id,
                    blood_bank_id=bank.blood_bank_id,
                    hospital_id=case.selected_hospital_id,
                    blood_group=blood_group,
                    units_requested=BLOOD_UNITS_PER_CASE,
                    hold_status=HoldStatus.pending,
                )
            )

    db.commit()
    db.refresh(check)
    return check


def list_holds(db: Session, blood_bank_id: str | None = None) -> list[BloodBankHold]:
    stmt = select(BloodBankHold).order_by(BloodBankHold.requested_at.desc())
    if blood_bank_id:
        stmt = stmt.where(BloodBankHold.blood_bank_id == blood_bank_id)
    return list(db.scalars(stmt))


def decide_hold(db: Session, hold_id: str, *, confirm: bool, decided_by: str) -> BloodBankHold:
    hold = db.get(BloodBankHold, hold_id)
    if hold is None:
        raise HoldDecisionError(f"hold '{hold_id}' not found")
    if hold.hold_status != HoldStatus.pending:
        raise HoldDecisionError(f"hold already {hold.hold_status.value}")
    hold.hold_status = HoldStatus.confirmed if confirm else HoldStatus.rejected
    hold.decided_at = datetime.now(timezone.utc)
    hold.decided_by = decided_by
    db.commit()
    db.refresh(hold)
    return hold


def list_blood_banks(db: Session) -> list[BloodBank]:
    return list(db.scalars(select(BloodBank).order_by(BloodBank.blood_bank_id)))
