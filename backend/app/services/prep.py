"""FR-6 orchestration: generate baseline + symptom-based prep actions, confirm one.

Explainable in one sentence: every bed-locked case gets three baseline prep
actions, plus one per matching symptom from a fixed lookup table, and a human
must tap each to confirm it.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BASELINE_PREP_ACTIONS, SYMPTOM_TO_PREP_ACTIONS
from app.models.assessment import Assessment
from app.models.case import Case
from app.models.prep import PrepAction, PrepActionStatus, PrepActionType


class PrepActionNotFound(Exception):
    pass


class PrepActionAlreadyConfirmed(Exception):
    pass


def list_for_case(db: Session, case_id: str) -> list[PrepAction]:
    return list(
        db.scalars(
            select(PrepAction)
            .where(PrepAction.case_id == case_id)
            .order_by(PrepAction.action_type, PrepAction.created_at, PrepAction.action_key)
        )
    )


def generate_for_case(db: Session, case: Case) -> list[PrepAction]:
    """Idempotent. Called once, right after a hospital is selected + bed-locked."""
    existing = list_for_case(db, case.case_id)
    if existing:
        return existing

    assessment = db.scalar(select(Assessment).where(Assessment.case_id == case.case_id))
    symptoms = list(assessment.symptom_checklist) if assessment else []

    rows: list[PrepAction] = []
    seen: set[str] = set()

    for spec in BASELINE_PREP_ACTIONS:
        seen.add(spec["action_key"])
        rows.append(
            PrepAction(
                case_id=case.case_id,
                hospital_id=case.selected_hospital_id,
                action_type=PrepActionType.baseline,
                status=PrepActionStatus.pending,
                triggered_by_symptom=None,
                **spec,
            )
        )

    for symptom in symptoms:
        for spec in SYMPTOM_TO_PREP_ACTIONS.get(symptom, []):
            if spec["action_key"] in seen:
                continue  # e.g. visible_bleeding + trauma both map to blood_bank_alert
            seen.add(spec["action_key"])
            rows.append(
                PrepAction(
                    case_id=case.case_id,
                    hospital_id=case.selected_hospital_id,
                    action_type=PrepActionType.symptom_based,
                    status=PrepActionStatus.pending,
                    triggered_by_symptom=symptom,
                    **spec,
                )
            )

    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return rows


def confirm(db: Session, prep_action_id: str, *, confirmed_by: str) -> PrepAction:
    """The ONLY place a prep_action becomes 'confirmed'. Explicit receptionist tap."""
    action = db.get(PrepAction, prep_action_id)
    if action is None:
        raise PrepActionNotFound(prep_action_id)
    if action.status == PrepActionStatus.confirmed:
        raise PrepActionAlreadyConfirmed(prep_action_id)

    action.status = PrepActionStatus.confirmed
    action.confirmed_by = confirmed_by
    action.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(action)
    return action
