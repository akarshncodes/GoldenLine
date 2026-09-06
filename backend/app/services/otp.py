"""FR-12: OTP request / verify. Codes are 'sent' through the shared SMS stub
(app/services/sms.py) and logged — verify against what was logged.
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import OTP_CODE_LENGTH, OTP_TTL_MINUTES
from app.models.auth import OtpVerification, Role, User
from app.models.sms import SmsCategory
from app.services.security import mint_token
from app.services.sms import send_sms


class OtpError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def request_otp(db: Session, phone_number: str) -> OtpVerification:
    code = "".join(secrets.choice("0123456789") for _ in range(OTP_CODE_LENGTH))
    row = OtpVerification(
        phone_number=phone_number,
        code=code,
        expires_at=_utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(row)
    db.flush()
    send_sms(
        db,
        phone_number,
        f"Your emergency verification code is {code}. It expires in {OTP_TTL_MINUTES} minutes.",
        category=SmsCategory.otp,
    )
    db.commit()
    db.refresh(row)
    return row


def _family_user_for(db: Session, phone_number: str) -> User:
    user = db.scalar(
        select(User).where(User.role == Role.family, User.phone_number == phone_number)
    )
    if user is None:
        user = User(
            user_id=f"family:{phone_number}",
            role=Role.family,
            display_name=f"Family {phone_number[-4:]}",
            phone_number=phone_number,
        )
        db.add(user)
        db.flush()
    return user


def verify_otp(db: Session, otp_verification_id: str, code: str) -> tuple[OtpVerification, str]:
    row = db.get(OtpVerification, otp_verification_id)
    if row is None or row.code != code:
        raise OtpError("invalid code")
    if row.expires_at <= _utcnow():
        raise OtpError("code expired")
    if row.consumed_at is not None:
        raise OtpError("code already used")

    if row.verified_at is None:
        row.verified_at = _utcnow()
    user = _family_user_for(db, row.phone_number)
    db.commit()

    token = mint_token(
        user_id=user.user_id, role=Role.family.value, hospital_id=None,
        blood_bank_id=None, phone_number=user.phone_number,
    )
    return row, token


def consume_verified_otp(db: Session, otp_verification_id: str, phone_number: str) -> OtpVerification:
    """FR-12: Path A case creation must present a verified, unused OTP for this phone."""
    row = db.get(OtpVerification, otp_verification_id)
    if row is None:
        raise OtpError("otp not found")
    if row.phone_number != phone_number:
        raise OtpError("otp does not match this phone number")
    if row.verified_at is None:
        raise OtpError("otp not verified")
    if row.expires_at <= _utcnow():
        raise OtpError("otp expired")
    if row.consumed_at is not None:
        raise OtpError("otp already used for a case")
    row.consumed_at = _utcnow()
    db.flush()
    return row
