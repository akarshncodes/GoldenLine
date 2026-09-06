"""FR-17 Bed/Room Categories: capacity definitions beyond general+ICU.

Deliberately additive — never touches `Hospital.live_bed_count`/`live_icu_count`,
the columns FR-2 ranking and FR-3 bed-lock read from. See app/models/bed_category.py.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bed_category import BedCategory
from app.models.hospital import Hospital


class HospitalNotFound(Exception):
    pass


def list_for_hospital(db: Session, hospital_id: str) -> list[BedCategory]:
    return list(
        db.scalars(
            select(BedCategory)
            .where(BedCategory.hospital_id == hospital_id)
            .order_by(BedCategory.category_code)
        )
    )


def list_all(db: Session) -> list[BedCategory]:
    return list(db.scalars(select(BedCategory).order_by(BedCategory.hospital_id, BedCategory.category_code)))


def get_category(db: Session, hospital_id: str, category_code: str) -> BedCategory | None:
    return db.scalar(
        select(BedCategory).where(
            BedCategory.hospital_id == hospital_id, BedCategory.category_code == category_code
        )
    )


def upsert_category(db: Session, hospital_id: str, category_code: str, *, label: str, total_beds: int) -> BedCategory:
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise HospitalNotFound(f"hospital '{hospital_id}' does not exist")

    row = get_category(db, hospital_id, category_code)
    if row is None:
        row = BedCategory(hospital_id=hospital_id, category_code=category_code, label=label, total_beds=total_beds)
        db.add(row)
    else:
        row.label = label
        row.total_beds = total_beds
    db.commit()
    db.refresh(row)
    return row


def capacity_snapshot(db: Session, hospital_id: str) -> dict:
    hospital = db.get(Hospital, hospital_id)
    if hospital is None:
        raise HospitalNotFound(f"hospital '{hospital_id}' does not exist")
    return {
        "hospital_id": hospital_id,
        "general_total": hospital.live_bed_count,
        "icu_total": hospital.live_icu_count,
        "categories": list_for_hospital(db, hospital_id),
    }
