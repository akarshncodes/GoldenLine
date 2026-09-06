"""FR-1 refinement: follow-up case notes (2026-09-05).

Reads rely entirely on SecurityMiddleware's blanket /cases/{id}/* scoping
(same pattern as route.py, prep.py, etc. — no per-handler auth needed for a
GET). The POST needs one thing middleware doesn't check: which *role* the
caller is, since "can see this case" also covers hospital/family/admin, and
this channel is deliberately helper-authored only (see case_notes.py).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.auth import Role
from app.models.case import Case
from app.schemas.case_note import CaseNoteCreate, CaseNoteOut
from app.services import case_notes as svc
from app.services.access import require_roles
from app.services.auth_deps import get_principal

router = APIRouter(prefix="/cases/{case_id}/notes", tags=["case-notes"])


def _require_case(case_id: str, db: Session) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"case '{case_id}' does not exist")
    return case


@router.post("", response_model=CaseNoteOut, status_code=status.HTTP_201_CREATED)
def add_case_note(
    case_id: str, payload: CaseNoteCreate, request: Request, db: Session = Depends(get_db)
) -> CaseNoteOut:
    """A helper adds a follow-up note mid-case — never overwrites the
    assessment, never itself changes symptom_checklist/criticality_level."""
    _require_case(case_id, db)
    require_roles(get_principal(request), Role.helper)
    return svc.create_note(db, case_id=case_id, author_id=payload.author_id, text=payload.text)


@router.get("", response_model=list[CaseNoteOut])
def get_case_notes(case_id: str, db: Session = Depends(get_db)) -> list[CaseNoteOut]:
    _require_case(case_id, db)
    return svc.list_notes(db, case_id)
