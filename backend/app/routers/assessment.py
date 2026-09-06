"""FR-1 On-Scene Assessment endpoints, attached to an existing case_id."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.assessment import InputMethod
from app.models.case import Case
from app.schemas.assessment import (
    AssessmentResponse,
    ChecklistSubmission,
    ConfirmAssessmentRequest,
    DerivedChecklistResponse,
    MatchedKeywordOut,
    VoiceTranscribeRequest,
)
from app.services import assessment as svc

router = APIRouter(prefix="/cases/{case_id}/assessment", tags=["assessment"])


def _require_case(case_id: str, db: Session) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"case '{case_id}' does not exist",
        )
    return case


@router.post("/checklist", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def submit_checklist(
    case_id: str, payload: ChecklistSubmission, db: Session = Depends(get_db)
) -> AssessmentResponse:
    """Tap method: save criticality + symptom tags directly (confirm=true required)."""
    _require_case(case_id, db)
    return svc.save_assessment(
        db,
        case_id=case_id,
        criticality_level=payload.criticality_level,
        symptom_checklist=payload.symptom_checklist,
        input_method=InputMethod.checklist,
        raw_voice_transcript=None,
    )


@router.post("/voice", response_model=DerivedChecklistResponse)
def submit_voice(
    case_id: str, payload: VoiceTranscribeRequest, db: Session = Depends(get_db)
) -> DerivedChecklistResponse:
    """Voice method step 1: transcribe (stub) + derive the checklist. Nothing is saved."""
    _require_case(case_id, db)
    transcript = svc.transcribe_voice(payload.transcript, payload.language_code)
    derived = svc.derive_checklist_from_transcript(transcript)
    return DerivedChecklistResponse(
        case_id=case_id,
        criticality_level=derived.criticality_level,
        symptom_checklist=derived.symptom_checklist,
        matched_keywords=[MatchedKeywordOut(symptom=m.symptom, keyword=m.keyword) for m in derived.matches],
        raw_voice_transcript=transcript,
    )


@router.post("/confirm", response_model=AssessmentResponse, status_code=status.HTTP_201_CREATED)
def confirm_assessment(
    case_id: str, payload: ConfirmAssessmentRequest, db: Session = Depends(get_db)
) -> AssessmentResponse:
    """Voice method step 2: persist the reviewed checklist (confirm=true required)."""
    _require_case(case_id, db)
    return svc.save_assessment(
        db,
        case_id=case_id,
        criticality_level=payload.criticality_level,
        symptom_checklist=payload.symptom_checklist,
        input_method=InputMethod.voice,
        raw_voice_transcript=payload.raw_voice_transcript,
    )


@router.get("", response_model=AssessmentResponse)
def get_assessment(case_id: str, db: Session = Depends(get_db)) -> AssessmentResponse:
    _require_case(case_id, db)
    assessment = svc.get_assessment(db, case_id)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"no assessment logged yet for case '{case_id}'",
        )
    return assessment
