"""Canonical seed data for FR-4 waypoints and FR-5 blood banks.

Mirrored inline in migrations 0009 / 0010 (frozen snapshots); guarded by
tests/test_fr4_fr5_seed_parity.py.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.blood import BloodBank
from app.models.route import Waypoint

SEED_WAYPOINTS: list[dict] = [
    {"waypoint_id": "WP-01", "name": "Anna Nagar PHC", "kind": "PHC",
     "latitude": 10.3745, "longitude": 77.9840, "has_oxygen": True, "has_doctor": True},
    {"waypoint_id": "WP-02", "name": "Nagal Nagar CHC", "kind": "CHC",
     "latitude": 10.3600, "longitude": 77.9830, "has_oxygen": True, "has_doctor": True},
    {"waypoint_id": "WP-03", "name": "Begampur PHC", "kind": "PHC",
     "latitude": 10.3580, "longitude": 77.9740, "has_oxygen": True, "has_doctor": False},
    {"waypoint_id": "WP-04", "name": "Gandhiji Nagar CHC", "kind": "CHC",
     "latitude": 10.3660, "longitude": 77.9880, "has_oxygen": True, "has_doctor": True},
    {"waypoint_id": "WP-05", "name": "New Agraharam PHC", "kind": "PHC",
     "latitude": 10.3710, "longitude": 77.9760, "has_oxygen": False, "has_doctor": True},
]

SEED_BLOOD_BANKS: list[dict] = [
    {"blood_bank_id": "BB-01", "name": "Government Head Quarters Hospital Blood Bank",
     "latitude": 10.3700, "longitude": 77.9820,
     "linked_hospital_ids": ["HOSP-001"],
     "stock_by_group": {"O-": 15, "O+": 35, "A+": 22, "A-": 6, "B+": 20, "B-": 5, "AB+": 7, "AB-": 3}},
    {"blood_bank_id": "BB-02", "name": "Dindigul Blood Bank",
     "latitude": 10.3660, "longitude": 77.9750,
     "linked_hospital_ids": [
         "HOSP-002", "HOSP-003", "HOSP-004", "HOSP-005", "HOSP-006", "HOSP-007",
         "HOSP-008", "HOSP-009", "HOSP-010", "HOSP-011", "HOSP-012", "HOSP-013",
     ],
     "stock_by_group": {"O-": 10, "O+": 25, "A+": 16, "B+": 12, "AB+": 5}},
    {"blood_bank_id": "BB-03", "name": "Indian Blood",
     "latitude": 10.3640, "longitude": 77.9790,
     "linked_hospital_ids": [
         "HOSP-014", "HOSP-015", "HOSP-016", "HOSP-017", "HOSP-018", "HOSP-019",
         "HOSP-020", "HOSP-021", "HOSP-022", "HOSP-023", "HOSP-024", "HOSP-025",
     ],
     "stock_by_group": {"O-": 6, "O+": 15, "A+": 10, "B+": 8}},
]


def seed_reference(db: Session) -> None:
    """Idempotent insert of waypoints + blood banks."""
    have_wp = set(db.scalars(select(Waypoint.waypoint_id)))
    for row in SEED_WAYPOINTS:
        if row["waypoint_id"] not in have_wp:
            db.add(Waypoint(**row))

    have_bb = set(db.scalars(select(BloodBank.blood_bank_id)))
    for row in SEED_BLOOD_BANKS:
        if row["blood_bank_id"] not in have_bb:
            db.add(BloodBank(**row))
    db.commit()
