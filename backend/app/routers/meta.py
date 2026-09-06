"""Public config the clients read + the FR-13 SMS fallback relay.

FR-14: the app UI language list and the FR-1 voice-input language list are the
SAME list — both derive from app.config.SUPPORTED_LANGUAGES.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import SUPPORTED_LANGUAGES
from app.database import get_db
from app.models.auth import Role
from app.models.sms import SmsCategory
from app.services.auth_deps import require_role
from app.services.security import Principal
from app.services.sms import send_sms

router = APIRouter(tags=["meta"])


@router.get("/languages")
def languages() -> dict:
    return {
        # ISO code -> English name of the language
        "supported": SUPPORTED_LANGUAGES,
        "codes": list(SUPPORTED_LANGUAGES),
        # FR-14 item 3: voice input (FR-1) uses exactly the same set
        "voice_input_codes": list(SUPPORTED_LANGUAGES),
        "default": "en",
    }


class SmsFallbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_phone: str = Field(min_length=6, max_length=15)
    message: str = Field(min_length=1, max_length=480)
    case_id: str | None = None
    category: str = "critical_update"


@router.post("/sms/fallback")
def sms_fallback(
    payload: SmsFallbackRequest,
    principal: Principal = Depends(require_role(Role.helper, Role.control_room)),
    db: Session = Depends(get_db),
) -> dict:
    """FR-13 item 3: the client calls this when it has no data connectivity for the
    family app but still has an SMS/thin channel, to push a critical status update."""
    row = send_sms(
        db, payload.to_phone, payload.message,
        category=SmsCategory.critical_update, case_id=payload.case_id,
    )
    db.commit()
    return {"sent": True, "channel": "sms", "sms_id": row.sms_id}
