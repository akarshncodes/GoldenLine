"""FR-12 OTP: request a code (stub SMS) and verify it."""
import re

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.services import otp as svc
from app.services import ratelimit

router = APIRouter(tags=["otp"])

_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


class OtpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def _valid(cls, v: str) -> str:
        if not _INDIAN_MOBILE.match(v or ""):
            raise ValueError("phone_number must be a 10-digit Indian mobile number")
        return v


class OtpRequestResponse(BaseModel):
    otp_verification_id: str
    phone_number: str
    note: str = "Code sent by SMS (stub) — see the sms_messages log."
    rate_limit_flagged: bool = False
    # Only populated when ENV=development, so local/test clients can complete the
    # flow without reading the SMS log. Removed in production.
    dev_code: str | None = None


class OtpVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    otp_verification_id: str = Field(min_length=1)
    code: str = Field(min_length=4, max_length=8)


class OtpVerifyResponse(BaseModel):
    verified: bool
    otp_verification_id: str
    access_token: str
    token_type: str = "bearer"


@router.post("/otp/request", response_model=OtpRequestResponse)
def request_otp(payload: OtpRequest, request: Request, db: Session = Depends(get_db)) -> OtpRequestResponse:
    row = svc.request_otp(db, payload.phone_number)
    flag = ratelimit.record_and_maybe_flag(
        db, source=f"phone:{payload.phone_number}", source_type="phone"
    )
    if flag is not None:
        db.commit()
    dev_code = row.code if get_settings().env == "development" else None
    return OtpRequestResponse(
        otp_verification_id=row.otp_verification_id,
        phone_number=payload.phone_number,
        rate_limit_flagged=flag is not None,
        dev_code=dev_code,
    )


@router.post("/otp/verify", response_model=OtpVerifyResponse)
def verify_otp(payload: OtpVerifyRequest, db: Session = Depends(get_db)) -> OtpVerifyResponse:
    try:
        row, token = svc.verify_otp(db, payload.otp_verification_id, payload.code)
    except svc.OtpError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return OtpVerifyResponse(verified=True, otp_verification_id=row.otp_verification_id, access_token=token)
