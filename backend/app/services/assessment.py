"""FR-1 On-Scene Assessment logic: voice stub, keyword derivation, persistence."""
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assessment import Assessment, CriticalityLevel, InputMethod, SymptomTag


def transcribe_voice(audio_or_text: str, language_code: str) -> str:
    """STUB speech-to-text.

    A real speech API will go here later (keyed by `language_code`). For now the
    input is assumed to be already-transcribed text and is returned unchanged.
    """
    return audio_or_text


# Keyword -> symptom tag. Matched as case-insensitive substrings of the transcript.
SYMPTOM_KEYWORDS: dict[SymptomTag, list[str]] = {
    SymptomTag.chest_pain: ["chest pain", "chest tightness", "chest pressure"],
    SymptomTag.breathing_difficulty: [
        "breathing difficulty", "difficulty breathing", "breathless",
        "short of breath", "can't breathe", "cannot breathe", "trouble breathing",
    ],
    SymptomTag.visible_bleeding: ["bleeding", "blood loss", "haemorrhage", "hemorrhage"],
    SymptomTag.trauma: ["trauma", "injury", "injured", "accident", "fracture", "broken bone", "fell", "fall"],
    SymptomTag.unconsciousness: ["unconscious", "unresponsive", "not responding", "fainted", "passed out"],
    SymptomTag.seizure: ["seizure", "convulsion", "convulsing", "fit", "fitting"],
    SymptomTag.severe_pain: ["severe pain", "extreme pain", "unbearable pain"],
    SymptomTag.burns: ["burn", "burnt", "burns", "scald"],
    SymptomTag.pregnancy_labour: ["pregnant", "pregnancy", "labour", "labor", "contractions", "water broke"],
    SymptomTag.stroke_signs: ["stroke", "face drooping", "slurred speech", "weakness on one side"],
    SymptomTag.high_fever: ["fever", "high temperature"],
    SymptomTag.vomiting: ["vomit", "vomiting", "throwing up"],
    SymptomTag.allergic_reaction: ["allergic", "allergy", "anaphylaxis", "hives", "swelling of the face"],
    SymptomTag.poisoning: ["poison", "poisoning", "overdose", "swallowed chemical"],
}

# Checked in this order; first match wins.
CRITICALITY_KEYWORDS: dict[CriticalityLevel, list[str]] = {
    CriticalityLevel.CRITICAL: [
        "critical", "severe", "unconscious", "not breathing", "no pulse", "cardiac arrest",
    ],
    CriticalityLevel.SERIOUS: ["serious", "moderate", "significant"],
    CriticalityLevel.STABLE: ["stable", "mild", "minor", "conscious and alert"],
}


@dataclass
class MatchedKeyword:
    symptom: SymptomTag
    keyword: str


@dataclass
class DerivedChecklist:
    criticality_level: CriticalityLevel | None = None
    symptom_checklist: list[SymptomTag] = field(default_factory=list)
    matches: list[MatchedKeyword] = field(default_factory=list)


def find_matched_keywords(text: str) -> list[MatchedKeyword]:
    """Every (symptom, keyword) pair whose keyword literally appears in `text`.

    Shared by the initial voice-derivation step and by case notes (FR-1
    refinement, 2026-09-05) — both let the helper *see* which words the system
    keyed off of, without ever silently changing the saved symptom checklist:
    this is presentation/trust-building only, never itself a write path.
    """
    lowered = text.lower()
    return [
        MatchedKeyword(symptom=tag, keyword=keyword)
        for tag, keywords in SYMPTOM_KEYWORDS.items()
        for keyword in keywords
        if keyword in lowered
    ]


def derive_checklist_from_transcript(transcript: str) -> DerivedChecklist:
    """Simple keyword matching — no LLM. Deterministic and explainable."""
    matches = find_matched_keywords(transcript)
    symptoms = list(dict.fromkeys(m.symptom for m in matches))

    text = transcript.lower()
    criticality: CriticalityLevel | None = None
    for level, keywords in CRITICALITY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            criticality = level
            break

    return DerivedChecklist(criticality_level=criticality, symptom_checklist=symptoms, matches=matches)


def get_assessment(db: Session, case_id: str) -> Assessment | None:
    return db.scalar(select(Assessment).where(Assessment.case_id == case_id))


def save_assessment(
    db: Session,
    *,
    case_id: str,
    criticality_level: CriticalityLevel,
    symptom_checklist: list[SymptomTag],
    input_method: InputMethod,
    raw_voice_transcript: str | None,
) -> Assessment:
    """Create or replace the single assessment for a case (1:1)."""
    assessment = get_assessment(db, case_id)
    tags = [t.value for t in symptom_checklist]

    if assessment is None:
        assessment = Assessment(case_id=case_id)
        db.add(assessment)

    assessment.criticality_level = criticality_level
    assessment.symptom_checklist = tags
    assessment.input_method = input_method
    assessment.raw_voice_transcript = raw_voice_transcript

    db.commit()
    db.refresh(assessment)
    return assessment
