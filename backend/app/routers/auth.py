"""FR-11 auth: password login (PBKDF2-hashed credentials), forgot/reset password,
and who-am-i.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.config import PASSWORD_MIN_LENGTH, get_settings
from app.database import get_db
from app.models.auth import User
from app.services import password_reset as reset_svc
from app.services.auth_deps import get_principal
from app.services.security import (
    DUMMY_PASSWORD_HASH,
    Principal,
    mint_token,
    verify_password,
)

router = APIRouter(tags=["auth"])

# One generic message for every failure mode so the response never reveals
# whether the account exists (no user enumeration).
_BAD_CREDENTIALS = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    "invalid account id or password",
    headers={"WWW-Authenticate": "Bearer"},
)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange a staff account id + password for a bearer token.

    Passwords are checked against a PBKDF2-HMAC-SHA256 hash (`users.password_hash`)
    in constant time. Seeded demo accounts use `"<user_id>.sih2026"` — a real
    deployment provisions real passwords and drops the seeds.
    """
    user = db.get(User, payload.user_id)
    # Always run a full verify — against a dummy hash when the account is missing
    # or has no password set — so the response time doesn't leak whether it exists.
    stored = user.password_hash if (user is not None and user.password_hash) else DUMMY_PASSWORD_HASH
    ok = verify_password(payload.password, stored)
    if user is None or not user.password_hash or not ok:
        raise _BAD_CREDENTIALS

    token = mint_token(
        user_id=user.user_id,
        role=user.role.value,
        hospital_id=user.hospital_id,
        blood_bank_id=user.blood_bank_id,
        phone_number=user.phone_number,
    )
    return TokenResponse(access_token=token, user_id=user.user_id, role=user.role.value)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=64)


class ForgotPasswordResponse(BaseModel):
    reset_token_id: str
    note: str = "A reset code was sent to the account's registered phone (if any)."
    # Only populated when ENV=development, so local/demo clients can complete the
    # flow without a real inbox — same convention as OTP's dev_code. Removed in prod.
    dev_code: str | None = None


@router.post("/auth/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)) -> ForgotPasswordResponse:
    """Start a password reset for a staff account id (FR-11)."""
    row = reset_svc.request_reset(db, payload.user_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown account")
    dev_code = row.code if get_settings().env == "development" else None
    return ForgotPasswordResponse(reset_token_id=row.reset_token_id, dev_code=dev_code)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reset_token_id: str = Field(min_length=1)
    code: str = Field(min_length=4, max_length=8)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=256)


@router.post("/auth/reset-password", response_model=TokenResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Complete a password reset and sign the account straight in (FR-11)."""
    try:
        user = reset_svc.reset_password(db, payload.reset_token_id, payload.code, payload.new_password)
    except reset_svc.PasswordResetError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    token = mint_token(
        user_id=user.user_id, role=user.role.value, hospital_id=user.hospital_id,
        blood_bank_id=user.blood_bank_id, phone_number=user.phone_number,
    )
    return TokenResponse(access_token=token, user_id=user.user_id, role=user.role.value)


@router.get("/auth/me", response_model=dict)
def whoami(principal: Principal = Depends(get_principal), db: Session = Depends(get_db)) -> dict:
    user = db.get(User, principal.user_id)
    return {
        "user_id": principal.user_id,
        "role": principal.role.value,
        "hospital_id": principal.hospital_id,
        "blood_bank_id": principal.blood_bank_id,
        "phone_number": principal.phone_number,
        "display_name": user.display_name if user is not None else principal.user_id,
    }
