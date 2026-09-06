"""FR-1 refinement: append-only follow-up notes for a case (2026-09-05).

Never touches Assessment's own criticality_level / symptom_checklist — those
stay the reviewed-once, structured, FR-1-safe fields. A note's matched
keywords are shown to the helper for awareness only; nothing here writes
back to the assessment automatically.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.case_note import CaseNote
from app.services.assessment import find_matched_keywords


def create_note(db: Session, *, case_id: str, author_id: str, text: str) -> CaseNote:
    matches = find_matched_keywords(text)
    note = CaseNote(
        case_id=case_id,
        author_id=author_id,
        text=text,
        matched_keywords=[{"symptom": m.symptom.value, "keyword": m.keyword} for m in matches],
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_notes(db: Session, case_id: str) -> list[CaseNote]:
    stmt = (
        select(CaseNote)
        .where(CaseNote.case_id == case_id)
        .order_by(CaseNote.created_at.desc())
    )
    return list(db.scalars(stmt))
