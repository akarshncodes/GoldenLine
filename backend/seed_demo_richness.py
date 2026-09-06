"""Populate every hospital with a realistic amount of demo data for judge
demos: FR-18 patient census (~50% bed occupancy), FR-19 staff roster (20+
doctors per hospital), FR-21 inventory (fully stocked).

Idempotent — safe to re-run. Each section skips a hospital that's already at
or above its target, so running this again after adding one more hospital (or
after nothing changed) is a fast no-op for everyone else.

`POST /admin/reset-demo-data` wipes the patient census (so the beds screen and
the census screen never disagree) but deliberately leaves the staff roster and
inventory alone — re-run this script afterward to restore the ~50%-occupied
look. See app/services/demo_reset.py for why the split is drawn there.

Usage (from the backend/ directory, with the venv active):
    python3 seed_demo_richness.py
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal
from app.models.case import Gender
from app.models.hospital import Hospital
from app.models.hospital_inventory import InventoryCategory
from app.models.hospital_staff import OnDutyStatus, StaffCategory
from app.models.patient import PatientStatus, PatientType
from app.services import hospital_inventory, hospital_staff, patients
from app.services.hospital_seed import SEED_HOSPITALS

random.seed(42)

FIRST_NAMES_M = [
    "Arun", "Karthik", "Manikandan", "Prakash", "Suresh", "Vignesh", "Bala",
    "Dinesh", "Gowtham", "Elango", "Prabhu", "Sathish", "Naveen", "Ravi",
    "Gopal", "Mohan", "Deepak", "Ashok", "Kumaresan", "Yuvaraj", "Selvam",
    "Murugan", "Saravanan", "Vijay", "Senthil", "Rajesh", "Anand", "Baskar",
]
FIRST_NAMES_F = [
    "Priya", "Lakshmi", "Kavya", "Divya", "Meena", "Anitha", "Revathi",
    "Saranya", "Kalaivani", "Nithya", "Deepa", "Vidya", "Sangeetha",
    "Bhavani", "Geetha", "Malar", "Suganya", "Kokila", "Yamuna", "Padma",
    "Vasanthi", "Shanthi", "Rani", "Devi", "Uma", "Indira",
]
SURNAMES = [
    "Murugan", "Palanisamy", "Rajendran", "Krishnan", "Subramaniam",
    "Chandran", "Natarajan", "Sivakumar", "Balasubramaniam", "Ganesan",
    "Ramasamy", "Velu", "Kandasamy", "Muthu", "Selvaraj", "Alagappan",
    "Perumal", "Ravichandran", "Thangaraj", "Manickam",
]

DOCTOR_SPECIALTY_MAP = {
    "cardiology": "Cardiology",
    "pulmonology": "Pulmonology",
    "neurology": "Neurology",
    "general_medicine": "General Medicine",
    "trauma_surgery": "Trauma Surgery",
    "obstetrics": "Obstetrics & Gynaecology",
    "burns_unit": "Burns & Plastic Surgery",
    "orthopedics": "Orthopaedics",
    "emergency": "Emergency Medicine",
}

INVENTORY_CATALOG = [
    ("Paracetamol 500mg tablets", InventoryCategory.medicine, "tablets", 4000, 500),
    ("Amoxicillin 500mg capsules", InventoryCategory.medicine, "capsules", 2500, 300),
    ("Ibuprofen 400mg tablets", InventoryCategory.medicine, "tablets", 3000, 400),
    ("Insulin (human, vials)", InventoryCategory.medicine, "vials", 300, 40),
    ("IV Normal Saline 500ml", InventoryCategory.medicine, "bottles", 800, 100),
    ("Adrenaline (epinephrine) injection", InventoryCategory.medicine, "ampoules", 200, 25),
    ("Atropine injection", InventoryCategory.medicine, "ampoules", 150, 20),
    ("Ceftriaxone injection", InventoryCategory.medicine, "vials", 400, 50),
    ("Surgical gloves", InventoryCategory.consumable, "pairs", 6000, 800),
    ("Syringes 5ml", InventoryCategory.consumable, "pieces", 5000, 600),
    ("IV cannula sets", InventoryCategory.consumable, "sets", 1500, 200),
    ("Gauze rolls", InventoryCategory.consumable, "rolls", 2000, 250),
    ("Suture kits", InventoryCategory.consumable, "kits", 600, 80),
    ("Oxygen masks", InventoryCategory.consumable, "pieces", 500, 60),
    ("Ventilators", InventoryCategory.equipment, "units", 12, 2),
    ("Defibrillators", InventoryCategory.equipment, "units", 8, 2),
    ("Infusion pumps", InventoryCategory.equipment, "units", 25, 4),
    ("ECG machines", InventoryCategory.equipment, "units", 10, 2),
    ("Patient monitors", InventoryCategory.equipment, "units", 30, 5),
    ("N95 masks", InventoryCategory.ppe, "pieces", 3000, 400),
    ("PPE kits (gown+gloves+shield)", InventoryCategory.ppe, "kits", 800, 100),
    ("Hand sanitizer 500ml", InventoryCategory.ppe, "bottles", 400, 50),
    ("Wheelchairs", InventoryCategory.other, "units", 20, 4),
    ("Stretchers", InventoryCategory.other, "units", 15, 3),
]


def random_name(gender: str) -> str:
    first = random.choice(FIRST_NAMES_M if gender == "male" else FIRST_NAMES_F)
    return f"{first} {random.choice(SURNAMES)}"


def random_phone() -> str:
    return f"{random.choice('6789')}{random.randint(100000000, 999999999)}"


def seed_inventory(db, hospital: Hospital) -> int:
    existing_names = {i.item_name for i in hospital_inventory.list_for_hospital(db, hospital.hospital_id)}
    added = 0
    for name, category, unit, baseline, threshold in INVENTORY_CATALOG:
        if name in existing_names:
            continue
        qty = int(baseline * random.uniform(0.85, 1.2))
        hospital_inventory.create_item(
            db, hospital_id=hospital.hospital_id, item_name=name, category=category,
            unit=unit, quantity_on_hand=qty, low_stock_threshold=threshold,
            actor="system:demo_seed",
        )
        added += 1
    return added


def seed_staff(db, hospital: Hospital) -> tuple[int, int]:
    existing = hospital_staff.list_for_hospital(db, hospital.hospital_id, include_inactive=True)
    existing_doctors = sum(1 for s in existing if s.staff_category == StaffCategory.doctor)
    if existing_doctors >= 20:
        return (0, 0)

    doctor_target = random.randint(20, 26)
    specialty_pool = [DOCTOR_SPECIALTY_MAP.get(s, "General Medicine") for s in hospital.specialties] or ["General Medicine"]

    counts = {
        StaffCategory.doctor: doctor_target,
        StaffCategory.nurse: doctor_target,
        StaffCategory.technician: max(3, round(doctor_target * 0.3)),
        StaffCategory.support: max(2, round(doctor_target * 0.15)),
        StaffCategory.admin_staff: max(1, round(doctor_target * 0.1)),
    }

    created = []
    for category, count in counts.items():
        for _ in range(count):
            gender = random.choice(["male", "female"])
            specialty = random.choice(specialty_pool) if category == StaffCategory.doctor else None
            staff = hospital_staff.create_staff(
                db, hospital_id=hospital.hospital_id, full_name=random_name(gender),
                staff_category=category, specialty=specialty, phone_number=random_phone(),
                created_by="system:demo_seed",
            )
            created.append(staff)

    # a realistic on-duty mix: ~55% on_duty, ~35% off_duty (default), ~10% on_leave
    for staff in created:
        roll = random.random()
        if roll < 0.55:
            hospital_staff.set_on_duty_status(db, staff.staff_id, OnDutyStatus.on_duty)
        elif roll < 0.65:
            hospital_staff.set_on_duty_status(db, staff.staff_id, OnDutyStatus.on_leave)
        # else: leave at the create_staff default (off_duty)

    return (len(created), doctor_target)


def seed_bed_occupancy(db, hospital: Hospital, seed_row: dict) -> tuple[int, int]:
    admitted_general = 0
    admitted_icu = 0
    for p in patients.list_for_hospital(db, hospital.hospital_id):
        if p.status != PatientStatus.admitted or p.patient_type != PatientType.walk_in:
            continue
        active = patients.get_active_assignment(db, p.patient_id)
        if active is None:
            continue
        if active.category_code == "general":
            admitted_general += 1
        elif active.category_code == "ICU":
            admitted_icu += 1

    target_occupied_general = round(seed_row["live_bed_count"] * 0.5)
    target_occupied_icu = round(seed_row["live_icu_count"] * 0.5)
    target_available_general = seed_row["live_bed_count"] - target_occupied_general
    target_available_icu = seed_row["live_icu_count"] - target_occupied_icu

    db.refresh(hospital)
    need_general = max(0, hospital.live_bed_count - target_available_general)
    need_icu = max(0, hospital.live_icu_count - target_available_icu)

    new_general, new_icu = 0, 0
    for bed_type, need in (("general", need_general), ("ICU", need_icu)):
        for _ in range(need):
            gender = random.choice(["male", "female"])
            age = random.randint(18, 85)
            try:
                patient = patients.create_patient(
                    db, hospital_id=hospital.hospital_id, full_name=random_name(gender),
                    approx_age=age, gender=Gender(gender), patient_type=PatientType.walk_in,
                    created_by="system:demo_seed",
                )
                patients.admit(
                    db, patient.patient_id, category_code=bed_type, bed_label=None,
                    actor="system:demo_seed",
                )
            except Exception as exc:  # NoBedAvailable etc. — stop this bed_type, keep going
                print(f"    ! stopped {bed_type} admits for {hospital.hospital_id}: {exc}")
                break
            if bed_type == "general":
                new_general += 1
            else:
                new_icu += 1

    return (new_general, new_icu)


def main():
    db = SessionLocal()
    seed_by_id = {h["hospital_id"]: h for h in SEED_HOSPITALS}
    try:
        hospitals = db.query(Hospital).order_by(Hospital.hospital_id).all()
        print(f"Seeding rich demo data for {len(hospitals)} hospitals...\n")
        for hospital in hospitals:
            seed_row = seed_by_id.get(hospital.hospital_id)
            if seed_row is None:
                continue
            inv_added = seed_inventory(db, hospital)
            staff_added, doctor_target = seed_staff(db, hospital)
            new_gen, new_icu = seed_bed_occupancy(db, hospital, seed_row)
            print(
                f"{hospital.hospital_id:10s} {hospital.name[:38]:38s} "
                f"inventory+{inv_added:<3d} staff+{staff_added:<4d}(doctors target {doctor_target}) "
                f"beds admitted +{new_gen} general / +{new_icu} ICU"
            )
    finally:
        db.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
