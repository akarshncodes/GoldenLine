"""Seed accounts (FR-11). Mirrored in migration 0016 (+ 0020 for password hashes);
guarded by parity tests.

Dev-only fixed accounts so the demo has one of every role. `family` users are
created on the fly during OTP verification (they authenticate by phone OTP, not
a password).

Every staff account has a password now (NFR 7.1 — never stored in plain text).
For the prototype each seeded account's password is derived from its id via
`dev_password(user_id)`; a real deployment sets real per-user passwords through
an admin/onboarding flow and these seeds are replaced.
"""
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.services.security import hash_password

# Prototype convention: seeded account "<id>" has password "<id>.<suffix>".
# Documented in the README; obviously not a real secret.
_DEV_PASSWORD_SUFFIX = "sih2026"


def dev_password(user_id: str) -> str:
    return f"{user_id}.{_DEV_PASSWORD_SUFFIX}"


@lru_cache(maxsize=None)
def _seed_password_hash(user_id: str) -> str:
    """Hash of a seed account's dev password, memoised per process.

    `seed_users()` runs only in local/test setup (the live server's accounts come
    from migration 0020), and the same 9 ids recur across every test's fresh DB —
    so caching turns ~9 PBKDF2 hashes *per test* into ~9 *per session*.
    """
    return hash_password(dev_password(user_id))


SEED_USERS: list[dict] = [
    {"user_id": "admin", "role": "admin", "display_name": "Platform Admin"},
    {"user_id": "control-room", "role": "control_room", "display_name": "Control Room"},
    # One helper per mock ambulance (app/services/ambulance.py FAKE_AMBULANCES,
    # 20 Dindigul-based vehicles) — a real 108-style dispatch always sends a
    # helper along with the driver. phone_number range 9600001XXX is distinct
    # from the ambulances' own driver_phone range (9600000XXX).
    {"user_id": "HLP-001", "role": "helper", "display_name": "Helper Selvam", "phone_number": "9600001001"},
    {"user_id": "HLP-002", "role": "helper", "display_name": "Helper Vijay Anand", "phone_number": "9600001002"},
    {"user_id": "HLP-003", "role": "helper", "display_name": "Helper Suresh Babu", "phone_number": "9600001003"},
    {"user_id": "HLP-004", "role": "helper", "display_name": "Helper Arun Prasad", "phone_number": "9600001004"},
    {"user_id": "HLP-005", "role": "helper", "display_name": "Helper Dinesh Kumar", "phone_number": "9600001005"},
    {"user_id": "HLP-006", "role": "helper", "display_name": "Helper Gowtham", "phone_number": "9600001006"},
    {"user_id": "HLP-007", "role": "helper", "display_name": "Helper Bala Murugan", "phone_number": "9600001007"},
    {"user_id": "HLP-008", "role": "helper", "display_name": "Helper Elango", "phone_number": "9600001008"},
    {"user_id": "HLP-009", "role": "helper", "display_name": "Helper Prabhu", "phone_number": "9600001009"},
    {"user_id": "HLP-010", "role": "helper", "display_name": "Helper Sathish Kumar", "phone_number": "9600001010"},
    {"user_id": "HLP-011", "role": "helper", "display_name": "Helper Naveen Kumar", "phone_number": "9600001011"},
    {"user_id": "HLP-012", "role": "helper", "display_name": "Helper Ravi Shankar", "phone_number": "9600001012"},
    {"user_id": "HLP-013", "role": "helper", "display_name": "Helper Gopal Krishnan", "phone_number": "9600001013"},
    {"user_id": "HLP-014", "role": "helper", "display_name": "Helper Mohan Raj", "phone_number": "9600001014"},
    {"user_id": "HLP-015", "role": "helper", "display_name": "Helper Deepak", "phone_number": "9600001015"},
    {"user_id": "HLP-016", "role": "helper", "display_name": "Helper Ashok Kumar", "phone_number": "9600001016"},
    {"user_id": "HLP-017", "role": "helper", "display_name": "Helper Kumaresan", "phone_number": "9600001017"},
    {"user_id": "HLP-018", "role": "helper", "display_name": "Helper Vignesh", "phone_number": "9600001018"},
    {"user_id": "HLP-019", "role": "helper", "display_name": "Helper Yuvaraj", "phone_number": "9600001019"},
    {"user_id": "HLP-020", "role": "helper", "display_name": "Helper Karthikeyan", "phone_number": "9600001020"},
    {"user_id": "recep-hosp-001", "role": "hospital_receptionist", "display_name": "Reception — Govt Medical College Hospital", "hospital_id": "HOSP-001"},
    {"user_id": "recep-hosp-004", "role": "hospital_receptionist", "display_name": "Reception — Sankara Hospital", "hospital_id": "HOSP-004"},
    {"user_id": "recep-hosp-007", "role": "hospital_receptionist", "display_name": "Reception — Shifa Multi Speciality Hospital", "hospital_id": "HOSP-007"},
    {"user_id": "coord-bb-01", "role": "blood_bank_coordinator", "display_name": "Coordinator — Govt HQ Hospital Blood Bank", "blood_bank_id": "BB-01"},
    {"user_id": "coord-bb-02", "role": "blood_bank_coordinator", "display_name": "Coordinator — Dindigul Blood Bank", "blood_bank_id": "BB-02"},
    {"user_id": "coord-bb-03", "role": "blood_bank_coordinator", "display_name": "Coordinator — Indian Blood", "blood_bank_id": "BB-03"},
]


def seed_users(db: Session) -> int:
    have = set(db.scalars(select(User.user_id)))
    n = 0
    for row in SEED_USERS:
        if row["user_id"] in have:
            continue
        db.add(User(**row, password_hash=_seed_password_hash(row["user_id"])))
        n += 1
    if n:
        db.commit()
    return n
