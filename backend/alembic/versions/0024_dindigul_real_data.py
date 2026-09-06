"""Replace the 10 fake hospitals / 3 fake blood banks / 5 fake-city ambulance
helpers with real Dindigul, Tamil Nadu data (this demo's single-city scope).

  - `hospitals`: the old 10 mock rows are replaced by 25 real Dindigul
    hospitals (HOSP-001 is the one real government hospital found for the
    city; the rest are real private hospitals — see
    app/services/hospital_seed.py's module docstring for the source/judgment
    calls). Names, approximate locations are real; bed counts, ratings,
    specialties-per-hospital and blood stock are invented — no public source
    for those exists.
  - `blood_banks`: BB-01/02/03 keep their ids but become the 3 real Dindigul
    blood banks found (Govt HQ Hospital Blood Bank, Dindigul Blood Bank,
    Indian Blood).
  - `users`: HLP-001..005 (yesterday's mock-city helpers) are renamed to match
    the new Dindigul ambulance roster, and 15 more (HLP-006..020) are added —
    one helper per mock ambulance now that there are 20
    (app/services/ambulance.py). Hospital-receptionist / blood-bank
    coordinator display names are updated to the new real names their
    hospital_id/blood_bank_id now point to (the ids themselves don't change).

Revision ID: 0024_dindigul_real_data
Revises: 0023_attender_to_helper_rename
Create Date: 2026-09-05
"""
import base64
import hashlib
import json
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0024_dindigul_real_data"
down_revision: Union[str, None] = "0023_attender_to_helper_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# mirrors app/services/hospital_seed.py SEED_HOSPITALS + hospital_sync.SEED_SYNC_TIERS
_HOSPITALS = [
    ("HOSP-001", "Government Medical College & Hospital, Dindigul",
     ["emergency", "cardiology", "pulmonology", "neurology", "general_medicine", "trauma_surgery", "obstetrics", "burns_unit"],
     130, 28, 3.2, 11, 3.9, "Government-Low", ["ayushman_bharat", "state_scheme"],
     10.3690, 77.9810, {"O-": 1, "O+": 20, "A+": 15, "B+": 12, "AB+": 4}, "hms_api"),
    ("HOSP-002", "St Joseph Hospital",
     ["emergency", "general_medicine", "trauma_surgery", "obstetrics"],
     60, 8, 2.1, 8, 4.0, "Private-Standard", ["state_scheme"],
     10.3705, 77.9850, {"O-": 4, "O+": 10, "A+": 6, "B+": 5}, "google_sheets"),
    ("HOSP-003", "Vadamalayan Hospital",
     ["emergency", "cardiology", "neurology", "general_medicine", "trauma_surgery", "pulmonology"],
     100, 20, 4.5, 14, 4.4, "Private-Premium", ["ayushman_bharat"],
     10.3620, 77.9870, {"O-": 8, "O+": 18, "A+": 10, "B+": 9, "AB+": 3}, "manual_counter"),
    ("HOSP-004", "Sankara Hospital",
     ["emergency", "cardiology", "general_medicine", "neurology"],
     70, 12, 3.8, 12, 4.2, "Private-Premium", [],
     10.3660, 77.9755, {"O-": 6, "O+": 14, "A+": 8, "B+": 6}, "google_sheets"),
    ("HOSP-005", "K.T. Super Speciality Hospitals",
     ["emergency", "cardiology", "neurology", "general_medicine", "trauma_surgery", "pulmonology"],
     80, 15, 2.9, 10, 4.3, "Private-Premium", ["ayushman_bharat"],
     10.3715, 77.9790, {"O-": 7, "O+": 16, "A+": 9, "B+": 7, "AB+": 2}, "hms_api"),
    ("HOSP-006", "Rajarajeswari Hospitals",
     ["emergency", "general_medicine", "obstetrics"],
     50, 6, 3.0, 10, 3.8, "Private-Standard", ["state_scheme"],
     10.3680, 77.9765, {"O-": 3, "O+": 8, "A+": 5}, "manual_counter"),
    ("HOSP-007", "Shifa Multi Speciality Hospital",
     ["emergency", "general_medicine", "trauma_surgery", "obstetrics"],
     55, 8, 1.8, 7, 3.9, "Private-Standard", ["ayushman_bharat", "state_scheme"],
     10.3665, 77.9825, {"O-": 5, "O+": 9, "A+": 6, "B+": 4}, "manual_counter"),
    ("HOSP-008", "JJ Arul Hospital",
     ["emergency", "general_medicine", "trauma_surgery"],
     45, 6, 5.5, 16, 3.7, "Private-Standard", [],
     10.3520, 77.9880, {"O-": 2, "O+": 7, "A+": 4}, "hms_api"),
    ("HOSP-009", "City Hospital",
     ["emergency", "general_medicine", "obstetrics", "pulmonology", "cardiology"],
     50, 7, 2.6, 9, 3.8, "Private-Standard", ["ayushman_bharat"],
     10.3730, 77.9800, {"O-": 6, "O+": 10, "A+": 6, "B+": 5}, "hms_api"),
    ("HOSP-010", "City Hospital Pavalam Trauma Centre",
     ["emergency", "trauma_surgery", "orthopedics"],
     40, 8, 2.4, 9, 3.9, "Private-Standard", [],
     10.3708, 77.9848, {"O-": 3, "O+": 8, "A+": 5}, "manual_counter"),
    ("HOSP-011", "Bharathi Mission Hospital",
     ["emergency", "general_medicine", "obstetrics"],
     40, 5, 3.5, 12, 3.6, "Private-Standard", ["state_scheme"],
     10.3745, 77.9770, {"O-": 2, "O+": 6, "A+": 4}, "manual_counter"),
    ("HOSP-012", "Best Hospital",
     ["emergency", "general_medicine", "pulmonology"],
     35, 5, 2.0, 8, 3.7, "Private-Standard", [],
     10.3675, 77.9795, {"O-": 3, "O+": 7, "A+": 4}, "google_sheets"),
    ("HOSP-013", "Hillock Hospital & Research Centre",
     ["emergency", "general_medicine", "neurology"],
     45, 6, 4.2, 13, 3.8, "Private-Standard", ["ayushman_bharat"],
     10.3600, 77.9950, {"O-": 4, "O+": 8, "A+": 5}, "hms_api"),
    ("HOSP-014", "JCB Hospitals",
     ["emergency", "general_medicine", "trauma_surgery"],
     40, 5, 1.6, 6, 3.7, "Private-Standard", [],
     10.3690, 77.9835, {"O-": 3, "O+": 7, "A+": 4}, "manual_counter"),
    ("HOSP-015", "Jeganath Hospital",
     ["emergency", "general_medicine"],
     30, 4, 1.9, 7, 3.5, "Private-Standard", [],
     10.3702, 77.9790, {"O-": 2, "O+": 5}, "manual_counter"),
    ("HOSP-016", "Dharshini Hospitals",
     ["emergency", "general_medicine", "obstetrics"],
     35, 4, 2.2, 8, 3.6, "Private-Standard", ["state_scheme"],
     10.3712, 77.9805, {"O-": 2, "O+": 6, "A+": 3}, "google_sheets"),
    ("HOSP-017", "S S Hospital",
     ["emergency", "general_medicine"],
     30, 4, 1.7, 6, 3.5, "Private-Standard", [],
     10.3695, 77.9798, {"O-": 2, "O+": 5}, "manual_counter"),
    ("HOSP-018", "Sai Hospitals",
     ["emergency", "general_medicine", "obstetrics"],
     35, 5, 3.9, 12, 3.6, "Private-Standard", [],
     10.3610, 77.9700, {"O-": 3, "O+": 6, "A+": 4}, "hms_api"),
    ("HOSP-019", "Saravana Hospital",
     ["emergency", "general_medicine"],
     30, 4, 1.5, 6, 3.6, "Private-Standard", [],
     10.3688, 77.9832, {"O-": 2, "O+": 5}, "manual_counter"),
    ("HOSP-020", "Shree Sathya Subha Hospital",
     ["emergency", "general_medicine", "obstetrics"],
     30, 3, 1.4, 5, 3.5, "Private-Standard", [],
     10.3699, 77.9788, {"O-": 1, "O+": 4}, "manual_counter"),
    ("HOSP-021", "Soba General Hospital",
     ["emergency", "general_medicine"],
     35, 4, 1.6, 6, 3.6, "Private-Standard", [],
     10.3693, 77.9791, {"O-": 2, "O+": 5}, "google_sheets"),
    ("HOSP-022", "Srivatsav Raksha Hospitals",
     ["emergency", "general_medicine", "trauma_surgery", "cardiology"],
     40, 6, 4.8, 15, 3.7, "Private-Standard", ["state_scheme"],
     10.3560, 77.9760, {"O-": 5, "O+": 9, "A+": 5}, "hms_api"),
    ("HOSP-023", "Vijaya Hospital",
     ["emergency", "general_medicine", "obstetrics", "pulmonology"],
     45, 6, 2.3, 8, 3.8, "Private-Standard", ["ayushman_bharat"],
     10.3716, 77.9815, {"O-": 3, "O+": 7, "A+": 5}, "manual_counter"),
    ("HOSP-024", "Kanna Hospital And Annai Velankanni Fertility Centre",
     ["emergency", "obstetrics"],
     25, 3, 2.7, 9, 3.7, "Private-Standard", [],
     10.3670, 77.9760, {"O-": 1, "O+": 4}, "manual_counter"),
    ("HOSP-025", "Aravind Eye Hospital",
     ["emergency"],
     20, 2, 3.6, 11, 4.5, "Private-Premium", [],
     10.3555, 77.9670, {"O-": 1, "O+": 3}, "google_sheets"),
]

# mirrors app/services/reference_seed.py SEED_BLOOD_BANKS
_BLOOD_BANKS = [
    ("BB-01", "Government Head Quarters Hospital Blood Bank", 10.3700, 77.9820,
     ["HOSP-001"],
     {"O-": 15, "O+": 35, "A+": 22, "A-": 6, "B+": 20, "B-": 5, "AB+": 7, "AB-": 3}),
    ("BB-02", "Dindigul Blood Bank", 10.3660, 77.9750,
     ["HOSP-002", "HOSP-003", "HOSP-004", "HOSP-005", "HOSP-006", "HOSP-007",
      "HOSP-008", "HOSP-009", "HOSP-010", "HOSP-011", "HOSP-012", "HOSP-013"],
     {"O-": 10, "O+": 25, "A+": 16, "B+": 12, "AB+": 5}),
    ("BB-03", "Indian Blood", 10.3640, 77.9790,
     ["HOSP-014", "HOSP-015", "HOSP-016", "HOSP-017", "HOSP-018", "HOSP-019",
      "HOSP-020", "HOSP-021", "HOSP-022", "HOSP-023", "HOSP-024", "HOSP-025"],
     {"O-": 6, "O+": 15, "A+": 10, "B+": 8}),
]

# mirrors app/services/user_seed.py SEED_USERS (HLP-001..020 block)
_HELPER_RENAMES = {
    "HLP-001": ("Helper Selvam", "9600001001"),
    "HLP-002": ("Helper Vijay Anand", "9600001002"),
    "HLP-003": ("Helper Suresh Babu", "9600001003"),
    "HLP-004": ("Helper Arun Prasad", "9600001004"),
    "HLP-005": ("Helper Dinesh Kumar", "9600001005"),
}
_NEW_HELPERS = [
    ("HLP-006", "Helper Gowtham", "9600001006"),
    ("HLP-007", "Helper Bala Murugan", "9600001007"),
    ("HLP-008", "Helper Elango", "9600001008"),
    ("HLP-009", "Helper Prabhu", "9600001009"),
    ("HLP-010", "Helper Sathish Kumar", "9600001010"),
    ("HLP-011", "Helper Naveen Kumar", "9600001011"),
    ("HLP-012", "Helper Ravi Shankar", "9600001012"),
    ("HLP-013", "Helper Gopal Krishnan", "9600001013"),
    ("HLP-014", "Helper Mohan Raj", "9600001014"),
    ("HLP-015", "Helper Deepak", "9600001015"),
    ("HLP-016", "Helper Ashok Kumar", "9600001016"),
    ("HLP-017", "Helper Kumaresan", "9600001017"),
    ("HLP-018", "Helper Vignesh", "9600001018"),
    ("HLP-019", "Helper Yuvaraj", "9600001019"),
    ("HLP-020", "Helper Karthikeyan", "9600001020"),
]
_RECEPTIONIST_RENAMES = {
    "recep-hosp-001": "Reception — Govt Medical College Hospital",
    "recep-hosp-004": "Reception — Sankara Hospital",
    "recep-hosp-007": "Reception — Shifa Multi Speciality Hospital",
}
_COORDINATOR_RENAMES = {
    "coord-bb-01": "Coordinator — Govt HQ Hospital Blood Bank",
    "coord-bb-02": "Coordinator — Dindigul Blood Bank",
}
_DEV_PASSWORD_SUFFIX = "sih2026"
_PBKDF2_ALGO = "pbkdf2_sha256"
_PBKDF2_ITERATIONS = 480_000


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _hash(plain: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{_PBKDF2_ALGO}${_PBKDF2_ITERATIONS}${_b64url(salt)}${_b64url(digest)}"


def upgrade() -> None:
    # --- hospitals: full replace (10 fake -> 25 real Dindigul) ---
    op.execute(sa.text("DELETE FROM hospital_sync_events"))
    op.execute(sa.text("DELETE FROM hospital_bed_reports"))
    op.execute(sa.text("DELETE FROM hospitals"))

    hospitals = sa.table(
        "hospitals",
        sa.column("hospital_id", sa.String),
        sa.column("name", sa.String),
        sa.column("specialties", sa.JSON),
        sa.column("live_bed_count", sa.Integer),
        sa.column("live_icu_count", sa.Integer),
        sa.column("distance_km", sa.Float),
        sa.column("eta_minutes", sa.Integer),
        sa.column("rating", sa.Float),
        sa.column("cost_tier", sa.String),
        sa.column("accepted_schemes", sa.JSON),
        sa.column("latitude", sa.Float),
        sa.column("longitude", sa.Float),
        sa.column("blood_stock_by_group", sa.JSON),
        sa.column("hospital_sync_tier", sa.String),
    )
    op.bulk_insert(
        hospitals,
        [
            {
                "hospital_id": h[0], "name": h[1], "specialties": h[2],
                "live_bed_count": h[3], "live_icu_count": h[4], "distance_km": h[5],
                "eta_minutes": h[6], "rating": h[7], "cost_tier": h[8],
                "accepted_schemes": h[9], "latitude": h[10], "longitude": h[11],
                "blood_stock_by_group": h[12], "hospital_sync_tier": h[13],
            }
            for h in _HOSPITALS
        ],
    )

    # --- blood banks: same 3 ids, real Dindigul content ---
    for bb_id, name, lat, lon, linked, stock in _BLOOD_BANKS:
        op.execute(
            sa.text(
                "UPDATE blood_banks SET name=:name, latitude=:lat, longitude=:lon, "
                "linked_hospital_ids=:linked, stock_by_group=:stock WHERE blood_bank_id=:id"
            ).bindparams(
                name=name, lat=lat, lon=lon,
                linked=json.dumps(linked), stock=json.dumps(stock), id=bb_id,
            )
        )

    # --- rename yesterday's 5 mock-city helpers to match the new Dindigul roster ---
    for hlp_id, (name, phone) in _HELPER_RENAMES.items():
        op.execute(
            sa.text(
                "UPDATE users SET display_name=:name, phone_number=:phone WHERE user_id=:id"
            ).bindparams(name=name, phone=phone, id=hlp_id)
        )

    # --- 15 more helpers, one per additional mock ambulance ---
    users = sa.table(
        "users",
        sa.column("user_id", sa.String),
        sa.column("role", sa.String),
        sa.column("display_name", sa.String),
        sa.column("phone_number", sa.String),
    )
    op.bulk_insert(
        users,
        [
            {"user_id": uid, "role": "helper", "display_name": name, "phone_number": phone}
            for uid, name, phone in _NEW_HELPERS
        ],
    )
    for uid, _name, _phone in _NEW_HELPERS:
        op.execute(
            sa.text("UPDATE users SET password_hash = :h WHERE user_id = :u").bindparams(
                h=_hash(f"{uid}.{_DEV_PASSWORD_SUFFIX}"), u=uid
            )
        )

    # --- receptionist / coordinator display names follow their hospital's/bank's new name ---
    for user_id, name in _RECEPTIONIST_RENAMES.items():
        op.execute(
            sa.text("UPDATE users SET display_name=:name WHERE user_id=:id").bindparams(name=name, id=user_id)
        )
    for user_id, name in _COORDINATOR_RENAMES.items():
        op.execute(
            sa.text("UPDATE users SET display_name=:name WHERE user_id=:id").bindparams(name=name, id=user_id)
        )

    # --- new BB-03 coordinator (BB-03 existed before but had no coordinator seeded) ---
    op.execute(
        sa.text(
            "INSERT INTO users (user_id, role, display_name, blood_bank_id) "
            "VALUES ('coord-bb-03', 'blood_bank_coordinator', 'Coordinator — Indian Blood', 'BB-03')"
        )
    )
    op.execute(
        sa.text("UPDATE users SET password_hash = :h WHERE user_id = 'coord-bb-03'").bindparams(
            h=_hash(f"coord-bb-03.{_DEV_PASSWORD_SUFFIX}")
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM users WHERE user_id = 'coord-bb-03'"))
    for user_id in _RECEPTIONIST_RENAMES:
        op.execute(sa.text("UPDATE users SET display_name='Reception' WHERE user_id=:id").bindparams(id=user_id))
    for user_id in _COORDINATOR_RENAMES:
        op.execute(sa.text("UPDATE users SET display_name='Coordinator' WHERE user_id=:id").bindparams(id=user_id))
    for uid, _name, _phone in _NEW_HELPERS:
        op.execute(sa.text("DELETE FROM users WHERE user_id = :u").bindparams(u=uid))
    for hlp_id in _HELPER_RENAMES:
        op.execute(sa.text("UPDATE users SET display_name='Helper' WHERE user_id=:id").bindparams(id=hlp_id))

    op.execute(sa.text("DELETE FROM hospital_sync_events"))
    op.execute(sa.text("DELETE FROM hospital_bed_reports"))
    op.execute(sa.text("DELETE FROM blood_banks"))
    op.execute(sa.text("DELETE FROM hospitals"))
    # Note: this downgrade does not restore the original 10 fake hospitals /
    # 3 fake blood banks verbatim — it only removes the Dindigul data. A full
    # round-trip back to the pre-2026-09-05 mock data would need re-running
    # migrations 0006/0008/0010's original inserts, which this migration
    # intentionally does not duplicate a second time.
