"""FR-11 (accounts/roles, deletion requests) + FR-12 (OTP, dedup, rate-limit) models."""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Role(str, enum.Enum):
    family = "family"
    helper = "helper"
    hospital_receptionist = "hospital_receptionist"
    blood_bank_coordinator = "blood_bank_coordinator"
    control_room = "control_room"
    admin = "admin"


class DeletionStatus(str, enum.Enum):
    pending = "pending"
    processed = "processed"
    rejected = "rejected"


def _new_id() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[Role] = mapped_column(SAEnum(Role, native_enum=False, length=24), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(10), nullable=True)     # family / helper
    hospital_id: Mapped[str | None] = mapped_column(String(32), nullable=True)      # hospital_receptionist
    blood_bank_id: Mapped[str | None] = mapped_column(String(32), nullable=True)    # blood_bank_coordinator
    # FR-11 / NFR 7.1: PBKDF2-HMAC-SHA256 encoded hash, never a plain-text password.
    # Nullable only so a freshly-provisioned account can exist before a password is
    # set; login rejects any account whose hash is unset.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class OtpVerification(Base):
    __tablename__ = "otp_verifications"

    otp_verification_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    phone_number: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # used to create a case


class DeletionRequest(Base):
    __tablename__ = "deletion_requests"

    deletion_request_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[DeletionStatus] = mapped_column(
        SAEnum(DeletionStatus, native_enum=False, length=12), nullable=False, default=DeletionStatus.pending
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DuplicateMergeLog(Base):
    """FR-12: records that a near-duplicate SOS was folded into an existing case."""
    __tablename__ = "duplicate_merge_logs"

    merge_log_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    primary_case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), nullable=False)
    duplicate_source: Mapped[str | None] = mapped_column(String(64), nullable=True)  # phone that re-triggered
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_metres: Mapped[float | None] = mapped_column(Float, nullable=True)
    seconds_apart: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class PasswordResetToken(Base):
    """FR-11: staff 'forgot password' — mirrors OtpVerification's shape/lifecycle.

    A reset needs BOTH the opaque `reset_token_id` (returned to the requester)
    AND the short `code` (delivered out-of-band — SMS when the account has a
    phone number, always shown on-screen in dev/demo mode) before a new
    password can be set. One-time use, short-lived.
    """
    __tablename__ = "password_reset_tokens"

    reset_token_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.user_id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RateLimitFlag(Base):
    """FR-12: flags a high request rate for review. Never blocks the request."""
    __tablename__ = "rate_limit_flags"

    rate_limit_flag_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    source: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'phone' | 'ip' | 'user'
    request_count: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
