"""FR-2: `hospitals` table + mock seed data (10 fake hospitals)

The seed is fixed reference data for the demo. `distance_km` / `eta_minutes` are
stand-ins that a real routing API would compute per case later.

Revision ID: 0006_fr2_hospitals
Revises: 0005_fr2_case_selection
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_fr2_hospitals"
down_revision: Union[str, None] = "0005_fr2_case_selection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SEED = [
    # id, name, specialties, beds, icu, dist_km, eta_min, rating, cost_tier, schemes
    ("HOSP-001", "City Government Hospital",
     ["emergency", "cardiology", "pulmonology", "neurology", "general_medicine", "trauma_surgery", "obstetrics"],
     12, 4, 3.2, 11, 3.8, "Government-Low", ["ayushman_bharat", "state_scheme"]),
    ("HOSP-002", "District General Hospital",
     ["emergency", "general_medicine", "obstetrics", "pulmonology"],
     8, 2, 6.5, 19, 3.5, "Government-Low", ["ayushman_bharat"]),
    ("HOSP-003", "Rural Referral Centre",
     ["emergency", "general_medicine"],
     5, 0, 9.0, 26, 3.0, "Government-Low", ["ayushman_bharat", "state_scheme"]),
    ("HOSP-004", "Metro Care Hospital",
     ["emergency", "cardiology", "neurology", "pulmonology", "general_medicine"],
     10, 5, 4.1, 13, 4.3, "Private-Standard", ["ayushman_bharat"]),
    ("HOSP-005", "Lakeside Multispecialty",
     ["emergency", "cardiology", "orthopedics", "trauma_surgery", "general_medicine"],
     7, 3, 5.0, 16, 4.0, "Private-Standard", ["state_scheme"]),
    ("HOSP-006", "Sunrise Community Hospital",
     ["emergency", "general_medicine", "obstetrics", "pulmonology"],
     9, 2, 7.8, 22, 3.6, "Private-Standard", []),
    ("HOSP-007", "Trauma & Burns Centre",
     ["emergency", "trauma_surgery", "burns_unit", "general_medicine", "orthopedics"],
     8, 4, 6.0, 18, 4.1, "Private-Standard", ["ayushman_bharat", "state_scheme"]),
    ("HOSP-008", "Apex Heart & Neuro Institute",
     ["emergency", "cardiology", "neurology", "cardiothoracic_surgery"],
     6, 6, 2.5, 9, 4.7, "Private-Premium", []),
    ("HOSP-009", "Grand Meridian Hospital",
     ["emergency", "cardiology", "neurology", "trauma_surgery", "general_medicine", "pulmonology", "burns_unit"],
     15, 8, 3.9, 12, 4.6, "Private-Premium", ["ayushman_bharat"]),
    ("HOSP-010", "Harbour Specialty Clinic",
     ["emergency", "general_medicine", "orthopedics"],
     4, 1, 8.4, 24, 3.9, "Private-Premium", []),
]


def upgrade() -> None:
    hospitals = op.create_table(
        "hospitals",
        sa.Column("hospital_id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("specialties", sa.JSON(), nullable=False),
        sa.Column("live_bed_count", sa.Integer(), nullable=False),
        sa.Column("live_icu_count", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("eta_minutes", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("cost_tier", sa.String(length=20), nullable=False),
        sa.Column("accepted_schemes", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "cost_tier IN ('Government-Low', 'Private-Standard', 'Private-Premium')",
            name="ck_hospitals_cost_tier",
        ),
    )
    op.bulk_insert(
        hospitals,
        [
            {
                "hospital_id": r[0], "name": r[1], "specialties": r[2],
                "live_bed_count": r[3], "live_icu_count": r[4], "distance_km": r[5],
                "eta_minutes": r[6], "rating": r[7], "cost_tier": r[8], "accepted_schemes": r[9],
            }
            for r in _SEED
        ],
    )


def downgrade() -> None:
    op.drop_table("hospitals")
