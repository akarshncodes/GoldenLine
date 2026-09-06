"""Minimal HMAC-SHA256 JWT + PBKDF2 password hashing + the request Principal (FR-11).

Hand-rolled on the Python standard library to avoid a new dependency; a production
deployment would swap in a vetted library and a real identity provider. Password
hashes use PBKDF2-HMAC-SHA256 (stdlib `hashlib`, FIPS-approved) — staff passwords
are NEVER stored in plain text (NFR 7.1).
"""
import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from app.config import get_settings
from app.models.auth import Role

def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# --- password hashing (PBKDF2-HMAC-SHA256, Django-style encoded string) --------
_PBKDF2_ALGO = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 480_000  # OWASP-recommended floor for PBKDF2-SHA256 (2023)
_SALT_BYTES = 16


class PasswordError(Exception):
    """Raised for an empty/invalid password on hashing."""


def hash_password(plain: str, *, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """Return an encoded hash: ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``."""
    if not plain:
        raise PasswordError("password must not be empty")
    salt = os.urandom(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return f"{_PBKDF2_ALGO}${iterations}${_b64url(salt)}${_b64url(digest)}"


def verify_password(plain: str, encoded: str | None) -> bool:
    """Constant-time check of ``plain`` against a stored encoded hash."""
    if not plain or not encoded:
        return False
    try:
        algo, iter_s, salt_b64, hash_b64 = encoded.split("$")
        if algo != _PBKDF2_ALGO:
            return False
        iterations = int(iter_s)
        salt = _b64url_decode(salt_b64)
        expected = _b64url_decode(hash_b64)
    except (ValueError, TypeError):
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


# A valid-format hash of an unguessable string. Verify against this when the
# account doesn't exist so login spends the same CPU whether or not it does.
DUMMY_PASSWORD_HASH = hash_password(_b64url(os.urandom(24)))


def needs_rehash(encoded: str | None) -> bool:
    """True if a stored hash uses a weaker parameter set than the current default."""
    if not encoded:
        return True
    try:
        algo, iter_s, _salt, _hash = encoded.split("$")
    except ValueError:
        return True
    return algo != _PBKDF2_ALGO or int(iter_s) < _PBKDF2_ITERATIONS


def mint_token(*, user_id: str, role: str, hospital_id: str | None, blood_bank_id: str | None,
               phone_number: str | None) -> str:
    settings = get_settings()
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "role": role,
        "hospital_id": hospital_id,
        "blood_bank_id": blood_bank_id,
        "phone_number": phone_number,
        "exp": int(time.time()) + settings.access_token_ttl_minutes * 60,
    }
    segments = [
        _b64url(json.dumps(header, separators=(",", ":")).encode()),
        _b64url(json.dumps(payload, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode()
    sig = hmac.new(settings.auth_secret.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64url(sig))
    return ".".join(segments)


class TokenError(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: Role
    hospital_id: str | None = None
    blood_bank_id: str | None = None
    phone_number: str | None = None

    @property
    def is_privileged(self) -> bool:
        return self.role in (Role.admin, Role.control_room)


def decode_token(token: str) -> Principal:
    settings = get_settings()
    try:
        h_b64, p_b64, sig_b64 = token.split(".")
    except ValueError as exc:
        raise TokenError("malformed token") from exc

    signing_input = f"{h_b64}.{p_b64}".encode()
    expected = hmac.new(settings.auth_secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
        raise TokenError("bad signature")

    payload = json.loads(_b64url_decode(p_b64))
    if payload.get("exp", 0) < time.time():
        raise TokenError("token expired")

    try:
        role = Role(payload["role"])
    except (KeyError, ValueError) as exc:
        raise TokenError("bad role") from exc

    return Principal(
        user_id=payload["sub"],
        role=role,
        hospital_id=payload.get("hospital_id"),
        blood_bank_id=payload.get("blood_bank_id"),
        phone_number=payload.get("phone_number"),
    )
