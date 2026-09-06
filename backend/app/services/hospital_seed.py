"""Canonical mock hospital seed data (FR-2, extended for FR-4/FR-5).

2026-09-05: replaced with real hospitals in Dindigul, Tamil Nadu (the city this
demo is now scoped to) — see memory/dindigul-real-data.md for the full source
list and judgment calls (specialty/tier assignment is inferred, not sourced;
bed counts/ratings/blood stock are invented; only names + approximate
locations are real). HOSP-001 is the one real government hospital found for
Dindigul city; there is deliberately no second or third Government-Low
hospital — the district's other government hospitals are taluk-level
facilities outside the city (out of scope, see memory note on geographic
scope).

The base 8 fields are inserted by migration 0006; the FR-4/FR-5 extras
(latitude, longitude, blood_stock_by_group) are backfilled by migration 0008.
A later migration (0024) replaces the original 10-hospital mock set with this
real-Dindigul one. Migrations are frozen snapshots and can't import this
module, so the values are duplicated there and guarded by
tests/test_fr4_fr5_seed_parity.py.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hospital import Hospital

SEED_HOSPITALS: list[dict] = [
    {"hospital_id": "HOSP-001", "name": "Government Medical College & Hospital, Dindigul",
     "specialties": ["emergency", "cardiology", "pulmonology", "neurology", "general_medicine", "trauma_surgery", "obstetrics", "burns_unit"],
     "live_bed_count": 130, "live_icu_count": 28, "distance_km": 3.2, "eta_minutes": 11,
     "rating": 3.9, "cost_tier": "Government-Low", "accepted_schemes": ["ayushman_bharat", "state_scheme"],
     "latitude": 10.3690, "longitude": 77.9810,
     "blood_stock_by_group": {"O-": 1, "O+": 20, "A+": 15, "B+": 12, "AB+": 4}},
    {"hospital_id": "HOSP-002", "name": "St Joseph Hospital",
     "specialties": ["emergency", "general_medicine", "trauma_surgery", "obstetrics"],
     "live_bed_count": 60, "live_icu_count": 8, "distance_km": 2.1, "eta_minutes": 8,
     "rating": 4.0, "cost_tier": "Private-Standard", "accepted_schemes": ["state_scheme"],
     "latitude": 10.3705, "longitude": 77.9850,
     "blood_stock_by_group": {"O-": 4, "O+": 10, "A+": 6, "B+": 5}},
    {"hospital_id": "HOSP-003", "name": "Vadamalayan Hospital",
     "specialties": ["emergency", "cardiology", "neurology", "general_medicine", "trauma_surgery", "pulmonology"],
     "live_bed_count": 100, "live_icu_count": 20, "distance_km": 4.5, "eta_minutes": 14,
     "rating": 4.4, "cost_tier": "Private-Premium", "accepted_schemes": ["ayushman_bharat"],
     "latitude": 10.3620, "longitude": 77.9870,
     "blood_stock_by_group": {"O-": 8, "O+": 18, "A+": 10, "B+": 9, "AB+": 3}},
    {"hospital_id": "HOSP-004", "name": "Sankara Hospital",
     "specialties": ["emergency", "cardiology", "general_medicine", "neurology"],
     "live_bed_count": 70, "live_icu_count": 12, "distance_km": 3.8, "eta_minutes": 12,
     "rating": 4.2, "cost_tier": "Private-Premium", "accepted_schemes": [],
     "latitude": 10.3660, "longitude": 77.9755,
     "blood_stock_by_group": {"O-": 6, "O+": 14, "A+": 8, "B+": 6}},
    {"hospital_id": "HOSP-005", "name": "K.T. Super Speciality Hospitals",
     "specialties": ["emergency", "cardiology", "neurology", "general_medicine", "trauma_surgery", "pulmonology"],
     "live_bed_count": 80, "live_icu_count": 15, "distance_km": 2.9, "eta_minutes": 10,
     "rating": 4.3, "cost_tier": "Private-Premium", "accepted_schemes": ["ayushman_bharat"],
     "latitude": 10.3715, "longitude": 77.9790,
     "blood_stock_by_group": {"O-": 7, "O+": 16, "A+": 9, "B+": 7, "AB+": 2}},
    {"hospital_id": "HOSP-006", "name": "Rajarajeswari Hospitals",
     "specialties": ["emergency", "general_medicine", "obstetrics"],
     "live_bed_count": 50, "live_icu_count": 6, "distance_km": 3.0, "eta_minutes": 10,
     "rating": 3.8, "cost_tier": "Private-Standard", "accepted_schemes": ["state_scheme"],
     "latitude": 10.3680, "longitude": 77.9765,
     "blood_stock_by_group": {"O-": 3, "O+": 8, "A+": 5}},
    {"hospital_id": "HOSP-007", "name": "Shifa Multi Speciality Hospital",
     "specialties": ["emergency", "general_medicine", "trauma_surgery", "obstetrics"],
     "live_bed_count": 55, "live_icu_count": 8, "distance_km": 1.8, "eta_minutes": 7,
     "rating": 3.9, "cost_tier": "Private-Standard", "accepted_schemes": ["ayushman_bharat", "state_scheme"],
     "latitude": 10.3665, "longitude": 77.9825,
     "blood_stock_by_group": {"O-": 5, "O+": 9, "A+": 6, "B+": 4}},
    {"hospital_id": "HOSP-008", "name": "JJ Arul Hospital",
     "specialties": ["emergency", "general_medicine", "trauma_surgery"],
     "live_bed_count": 45, "live_icu_count": 6, "distance_km": 5.5, "eta_minutes": 16,
     "rating": 3.7, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3520, "longitude": 77.9880,
     "blood_stock_by_group": {"O-": 2, "O+": 7, "A+": 4}},
    {"hospital_id": "HOSP-009", "name": "City Hospital",
     "specialties": ["emergency", "general_medicine", "obstetrics", "pulmonology", "cardiology"],
     "live_bed_count": 50, "live_icu_count": 7, "distance_km": 2.6, "eta_minutes": 9,
     "rating": 3.8, "cost_tier": "Private-Standard", "accepted_schemes": ["ayushman_bharat"],
     "latitude": 10.3730, "longitude": 77.9800,
     "blood_stock_by_group": {"O-": 6, "O+": 10, "A+": 6, "B+": 5}},
    {"hospital_id": "HOSP-010", "name": "City Hospital Pavalam Trauma Centre",
     "specialties": ["emergency", "trauma_surgery", "orthopedics"],
     "live_bed_count": 40, "live_icu_count": 8, "distance_km": 2.4, "eta_minutes": 9,
     "rating": 3.9, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3708, "longitude": 77.9848,
     "blood_stock_by_group": {"O-": 3, "O+": 8, "A+": 5}},
    {"hospital_id": "HOSP-011", "name": "Bharathi Mission Hospital",
     "specialties": ["emergency", "general_medicine", "obstetrics"],
     "live_bed_count": 40, "live_icu_count": 5, "distance_km": 3.5, "eta_minutes": 12,
     "rating": 3.6, "cost_tier": "Private-Standard", "accepted_schemes": ["state_scheme"],
     "latitude": 10.3745, "longitude": 77.9770,
     "blood_stock_by_group": {"O-": 2, "O+": 6, "A+": 4}},
    {"hospital_id": "HOSP-012", "name": "Best Hospital",
     "specialties": ["emergency", "general_medicine", "pulmonology"],
     "live_bed_count": 35, "live_icu_count": 5, "distance_km": 2.0, "eta_minutes": 8,
     "rating": 3.7, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3675, "longitude": 77.9795,
     "blood_stock_by_group": {"O-": 3, "O+": 7, "A+": 4}},
    {"hospital_id": "HOSP-013", "name": "Hillock Hospital & Research Centre",
     "specialties": ["emergency", "general_medicine", "neurology"],
     "live_bed_count": 45, "live_icu_count": 6, "distance_km": 4.2, "eta_minutes": 13,
     "rating": 3.8, "cost_tier": "Private-Standard", "accepted_schemes": ["ayushman_bharat"],
     "latitude": 10.3600, "longitude": 77.9950,
     "blood_stock_by_group": {"O-": 4, "O+": 8, "A+": 5}},
    {"hospital_id": "HOSP-014", "name": "JCB Hospitals",
     "specialties": ["emergency", "general_medicine", "trauma_surgery"],
     "live_bed_count": 40, "live_icu_count": 5, "distance_km": 1.6, "eta_minutes": 6,
     "rating": 3.7, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3690, "longitude": 77.9835,
     "blood_stock_by_group": {"O-": 3, "O+": 7, "A+": 4}},
    {"hospital_id": "HOSP-015", "name": "Jeganath Hospital",
     "specialties": ["emergency", "general_medicine"],
     "live_bed_count": 30, "live_icu_count": 4, "distance_km": 1.9, "eta_minutes": 7,
     "rating": 3.5, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3702, "longitude": 77.9790,
     "blood_stock_by_group": {"O-": 2, "O+": 5}},
    {"hospital_id": "HOSP-016", "name": "Dharshini Hospitals",
     "specialties": ["emergency", "general_medicine", "obstetrics"],
     "live_bed_count": 35, "live_icu_count": 4, "distance_km": 2.2, "eta_minutes": 8,
     "rating": 3.6, "cost_tier": "Private-Standard", "accepted_schemes": ["state_scheme"],
     "latitude": 10.3712, "longitude": 77.9805,
     "blood_stock_by_group": {"O-": 2, "O+": 6, "A+": 3}},
    {"hospital_id": "HOSP-017", "name": "S S Hospital",
     "specialties": ["emergency", "general_medicine"],
     "live_bed_count": 30, "live_icu_count": 4, "distance_km": 1.7, "eta_minutes": 6,
     "rating": 3.5, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3695, "longitude": 77.9798,
     "blood_stock_by_group": {"O-": 2, "O+": 5}},
    {"hospital_id": "HOSP-018", "name": "Sai Hospitals",
     "specialties": ["emergency", "general_medicine", "obstetrics"],
     "live_bed_count": 35, "live_icu_count": 5, "distance_km": 3.9, "eta_minutes": 12,
     "rating": 3.6, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3610, "longitude": 77.9700,
     "blood_stock_by_group": {"O-": 3, "O+": 6, "A+": 4}},
    {"hospital_id": "HOSP-019", "name": "Saravana Hospital",
     "specialties": ["emergency", "general_medicine"],
     "live_bed_count": 30, "live_icu_count": 4, "distance_km": 1.5, "eta_minutes": 6,
     "rating": 3.6, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3688, "longitude": 77.9832,
     "blood_stock_by_group": {"O-": 2, "O+": 5}},
    {"hospital_id": "HOSP-020", "name": "Shree Sathya Subha Hospital",
     "specialties": ["emergency", "general_medicine", "obstetrics"],
     "live_bed_count": 30, "live_icu_count": 3, "distance_km": 1.4, "eta_minutes": 5,
     "rating": 3.5, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3699, "longitude": 77.9788,
     "blood_stock_by_group": {"O-": 1, "O+": 4}},
    {"hospital_id": "HOSP-021", "name": "Soba General Hospital",
     "specialties": ["emergency", "general_medicine"],
     "live_bed_count": 35, "live_icu_count": 4, "distance_km": 1.6, "eta_minutes": 6,
     "rating": 3.6, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3693, "longitude": 77.9791,
     "blood_stock_by_group": {"O-": 2, "O+": 5}},
    {"hospital_id": "HOSP-022", "name": "Srivatsav Raksha Hospitals",
     "specialties": ["emergency", "general_medicine", "trauma_surgery", "cardiology"],
     "live_bed_count": 40, "live_icu_count": 6, "distance_km": 4.8, "eta_minutes": 15,
     "rating": 3.7, "cost_tier": "Private-Standard", "accepted_schemes": ["state_scheme"],
     "latitude": 10.3560, "longitude": 77.9760,
     "blood_stock_by_group": {"O-": 5, "O+": 9, "A+": 5}},
    {"hospital_id": "HOSP-023", "name": "Vijaya Hospital",
     "specialties": ["emergency", "general_medicine", "obstetrics", "pulmonology"],
     "live_bed_count": 45, "live_icu_count": 6, "distance_km": 2.3, "eta_minutes": 8,
     "rating": 3.8, "cost_tier": "Private-Standard", "accepted_schemes": ["ayushman_bharat"],
     "latitude": 10.3716, "longitude": 77.9815,
     "blood_stock_by_group": {"O-": 3, "O+": 7, "A+": 5}},
    {"hospital_id": "HOSP-024", "name": "Kanna Hospital And Annai Velankanni Fertility Centre",
     "specialties": ["emergency", "obstetrics"],
     "live_bed_count": 25, "live_icu_count": 3, "distance_km": 2.7, "eta_minutes": 9,
     "rating": 3.7, "cost_tier": "Private-Standard", "accepted_schemes": [],
     "latitude": 10.3670, "longitude": 77.9760,
     "blood_stock_by_group": {"O-": 1, "O+": 4}},
    {"hospital_id": "HOSP-025", "name": "Aravind Eye Hospital",
     "specialties": ["emergency"],
     "live_bed_count": 20, "live_icu_count": 2, "distance_km": 3.6, "eta_minutes": 11,
     "rating": 4.5, "cost_tier": "Private-Premium", "accepted_schemes": [],
     "latitude": 10.3555, "longitude": 77.9670,
     "blood_stock_by_group": {"O-": 1, "O+": 3}},
]


# FR-16: the sync tier each seed hospital is on. `hospital_sync.SEED_SYNC_TIERS`
# is the single source of truth; migration 0019 mirrors it (guarded by
# tests/test_fr4_fr5_seed_parity.py).
from app.services.hospital_sync import SEED_SYNC_TIERS  # noqa: E402

for _h in SEED_HOSPITALS:
    _h.setdefault("hospital_sync_tier", SEED_SYNC_TIERS[_h["hospital_id"]])
    # Fixed total capacity == the starting live count — see Hospital.total_bed_count.
    _h.setdefault("total_bed_count", _h["live_bed_count"])
    _h.setdefault("total_icu_bed_count", _h["live_icu_count"])


def seed_hospitals(db: Session) -> int:
    """Insert any missing seed hospitals. Idempotent. Returns rows inserted."""
    existing = set(db.scalars(select(Hospital.hospital_id)))
    inserted = 0
    for row in SEED_HOSPITALS:
        if row["hospital_id"] not in existing:
            db.add(Hospital(**row))
            inserted += 1
    if inserted:
        db.commit()
    return inserted
