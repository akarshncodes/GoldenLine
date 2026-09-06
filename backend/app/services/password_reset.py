"""FR-11: staff "forgot password" — mirrors the FR-12 OTP request/verify shape.

Two steps, both required before a password changes:
  1. `request_reset(user_id)` — mints a `PasswordResetToken` (opaque id + short
     code), sends the code by SMS when the account has a phone number (through
     the one shared SMS seam), and always returns the row so the caller can
     decide whether to surface a dev code (dev/demo mode only, same as OTP).
  2. `reset_password(reset_token_id, code, new_password)` — verifies the code
     matches, is unexpired and unused, then hashes the new password. One-time use.

Deliberate choice: `request_reset` returns `None` for an unknown account and the
router turns that into a 404. Unlike a public sign-up product, GoldenLine's staff
account ids are internal usernames handed out at onboarding, not secrets or
personal emails — so confirming "no such account" here does not expose anything
a coworker couldn't already see on the roster, and it keeps the reset flow usable
without a real inbox to check.
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import PASSWORD_RESET_CODE_LENGTH, PASSWORD_RESET_TTL_MINUTES
from app.models.auth import PasswordResetToken, User
from app.models.sms import SmsCategory
from app.services.security import hash_password
from app.services.sms import send_sms


class PasswordResetError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def request_reset(db: Session, user_id: str) -> PasswordResetToken | None:
    user = db.get(User, user_id)
    if user is None:
        return None

    code = "".join(secrets.choice("0123456789") for _ in range(PASSWORD_RESET_CODE_LENGTH))
    row = PasswordResetToken(
        user_id=user_id,
        code=code,
        expires_at=_utcnow() + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES),
    )
    db.add(row)
    db.flush()

    if user.phone_number:
        send_sms(
            db, user.phone_number,
            f"Your GoldenLine password reset code is {code}. It expires in "
            f"{PASSWORD_RESET_TTL_MINUTES} minutes. Didn't request this? Ignore it.",
            category=SmsCategory.password_reset,
        )

    db.commit()
    db.refresh(row)
    return row


def reset_password(db: Session, reset_token_id: str, code: str, new_password: str) -> User:
    row = db.get(PasswordResetToken, reset_token_id)
    if row is None or row.code != code:
        raise PasswordResetError("invalid reset code")
    if row.expires_at <= _utcnow():
        raise PasswordResetError("reset code expired")
    if row.used_at is not None:
        raise PasswordResetError("reset code already used")

    user = db.get(User, row.user_id)
    if user is None:
        raise PasswordResetError("account no longer exists")

    user.password_hash = hash_password(new_password)
    row.used_at = _utcnow()
    db.commit()
    db.refresh(user)
    return user
