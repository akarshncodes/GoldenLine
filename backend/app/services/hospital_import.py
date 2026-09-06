"""FR-22 Rule-Based Fuzzy Import: orchestration.

Fetches/parses a CSV (upload or Google Sheet), runs `import_matching`, stores
the parsed rows + suggested mapping as an `ImportSession` (the review UI edits
this before committing), then on commit loops each target table's OWN
create-service function per row — reusing FR-17/18/19/21's validation instead
of duplicating it, exactly like every prior phase's own write-path.

Two-step preview/confirm flow: preview never writes real data, only a
session row; commit is the only place that does, and only after the caller
has (optionally) overridden the suggested column mapping.
"""
import csv
import io
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models.case import Gender
from app.models.hospital import Hospital
from app.models.hospital_inventory import InventoryCategory
from app.models.hospital_staff import StaffCategory
from app.models.import_session import ImportSession
from app.models.patient import PatientType
from app.services import bed_categories as bed_cat_svc
from app.services import hospital_inventory as inv_svc
from app.services import hospital_staff as staff_svc
from app.services import patients as patients_svc
from app.services.import_matching import REQUIRED_FIELDS, TARGET_TABLES, suggest_column_mapping


class HospitalNotFound(Exception):
    pass


class UnknownTargetTable(Exception):
    pass


class InvalidImportFile(Exception):
    pass


class ImportSessionNotFound(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_csv(text: str) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    rows = [dict(row) for row in reader]
    return headers, rows


# --------------------------------------------------------------- fetch + preview
# Real Google Sheet ids are ~44 url-safe chars; require >=20 (same threshold
# hospital_sync.py uses) so this never has a "demo mode" — import needs real
# structured columns, unlike FR-16's narrow ?general=&icu= shortcut.
_GSHEET_ID_RE = re.compile(r"docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,})")


def _fetch_sheet_csv(sheet_url: str) -> str:
    match = _GSHEET_ID_RE.search(sheet_url or "")
    if not match:
        raise InvalidImportFile("not a recognised Google Sheets URL")
    export_url = f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=csv"
    resp = httpx.get(export_url, timeout=10.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def preview_from_rows(
    db: Session, *, hospital_id: str, target_table: str, headers: list[str], rows: list[dict], actor: str
) -> ImportSession:
    if db.get(Hospital, hospital_id) is None:
        raise HospitalNotFound(f"hospital '{hospital_id}' does not exist")
    if target_table not in TARGET_TABLES:
        raise UnknownTargetTable(f"unknown target_table '{target_table}'")

    session = ImportSession(
        hospital_id=hospital_id,
        target_table=target_table,
        raw_rows=rows,
        suggested_mapping=suggest_column_mapping(headers, target_table),
        created_by=actor,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def preview_from_csv_text(
    db: Session, *, hospital_id: str, target_table: str, csv_text: str, actor: str
) -> ImportSession:
    headers, rows = _parse_csv(csv_text)
    if not headers:
        raise InvalidImportFile("could not parse any columns from the file")
    return preview_from_rows(
        db, hospital_id=hospital_id, target_table=target_table, headers=headers, rows=rows, actor=actor
    )


def preview_from_sheet(
    db: Session, *, hospital_id: str, target_table: str, sheet_url: str, actor: str
) -> ImportSession:
    csv_text = _fetch_sheet_csv(sheet_url)
    return preview_from_csv_text(
        db, hospital_id=hospital_id, target_table=target_table, csv_text=csv_text, actor=actor
    )


def get_session(db: Session, import_session_id: str) -> ImportSession | None:
    return db.get(ImportSession, import_session_id)


def match_report(session: ImportSession) -> dict:
    sample_rows = session.raw_rows[:3]
    columns = []
    unmatched = []
    for col in session.suggested_mapping:
        source = col["source_column"]
        entry = {**col, "sample_values": [str(r.get(source, "") or "") for r in sample_rows]}
        columns.append(entry)
        if col["matched_field"] is None:
            unmatched.append(source)
    return {
        "import_session_id": session.import_session_id,
        "target_table": session.target_table,
        "row_count": len(session.raw_rows),
        "columns": columns,
        "unmatched_columns": unmatched,
    }


# --------------------------------------------------------------- commit
def _build_patient(db: Session, *, hospital_id: str, row: dict, actor: str) -> None:
    full_name = (row.get("full_name") or "").strip()
    if not full_name:
        raise ValueError("missing required field 'full_name'")

    approx_age = None
    if row.get("approx_age"):
        try:
            approx_age = int(float(row["approx_age"]))
        except (TypeError, ValueError):
            raise ValueError(f"invalid approx_age '{row['approx_age']}'")

    gender = None
    gender_raw = (row.get("gender") or "").strip().lower()
    if gender_raw:
        if gender_raw not in Gender.__members__:
            raise ValueError(f"invalid gender '{row['gender']}'")
        gender = Gender(gender_raw)

    phone_number = (row.get("phone_number") or "").strip() or None

    type_raw = (row.get("patient_type") or "").strip().lower().replace(" ", "_") or "walk_in"
    if type_raw not in ("walk_in", "scheduled"):
        raise ValueError(f"invalid patient_type '{row.get('patient_type')}'")

    patients_svc.create_patient(
        db, hospital_id=hospital_id, full_name=full_name, approx_age=approx_age,
        gender=gender, phone_number=phone_number, patient_type=PatientType(type_raw), created_by=actor,
    )


def _build_staff(db: Session, *, hospital_id: str, row: dict, actor: str) -> None:
    full_name = (row.get("full_name") or "").strip()
    if not full_name:
        raise ValueError("missing required field 'full_name'")

    cat_raw = (row.get("staff_category") or "").strip().lower().replace(" ", "_")
    if cat_raw not in StaffCategory.__members__:
        raise ValueError(f"invalid staff_category '{row.get('staff_category')}'")

    specialty = (row.get("specialty") or "").strip() or None
    phone_number = (row.get("phone_number") or "").strip() or None

    staff_svc.create_staff(
        db, hospital_id=hospital_id, full_name=full_name, staff_category=StaffCategory(cat_raw),
        specialty=specialty, phone_number=phone_number, created_by=actor,
    )


def _build_inventory_item(db: Session, *, hospital_id: str, row: dict, actor: str) -> None:
    item_name = (row.get("item_name") or "").strip()
    if not item_name:
        raise ValueError("missing required field 'item_name'")

    cat_raw = (row.get("category") or "").strip().lower()
    if cat_raw not in InventoryCategory.__members__:
        raise ValueError(f"invalid category '{row.get('category')}'")

    unit = (row.get("unit") or "").strip()
    if not unit:
        raise ValueError("missing required field 'unit'")

    quantity = 0
    if row.get("quantity_on_hand"):
        try:
            quantity = int(float(row["quantity_on_hand"]))
        except (TypeError, ValueError):
            raise ValueError(f"invalid quantity_on_hand '{row['quantity_on_hand']}'")

    threshold = None
    if row.get("low_stock_threshold"):
        try:
            threshold = int(float(row["low_stock_threshold"]))
        except (TypeError, ValueError):
            raise ValueError(f"invalid low_stock_threshold '{row['low_stock_threshold']}'")

    inv_svc.create_item(
        db, hospital_id=hospital_id, item_name=item_name, category=InventoryCategory(cat_raw), unit=unit,
        quantity_on_hand=quantity, low_stock_threshold=threshold, actor=actor,
    )


def _build_bed_category(db: Session, *, hospital_id: str, row: dict, actor: str) -> None:
    code = (row.get("category_code") or "").strip().lower().replace(" ", "_")
    if not code:
        raise ValueError("missing required field 'category_code'")
    label = (row.get("label") or "").strip()
    if not label:
        raise ValueError("missing required field 'label'")
    if not row.get("total_beds"):
        raise ValueError("missing required field 'total_beds'")
    try:
        total_beds = int(float(row["total_beds"]))
    except (TypeError, ValueError):
        raise ValueError(f"invalid total_beds '{row['total_beds']}'")

    bed_cat_svc.upsert_category(db, hospital_id, code, label=label, total_beds=total_beds)


_ROW_BUILDERS = {
    "patients": _build_patient,
    "hospital_staff": _build_staff,
    "hospital_inventory_items": _build_inventory_item,
    "bed_categories": _build_bed_category,
}


def commit_import(
    db: Session, import_session_id: str, *, column_mapping: dict[str, str | None], actor: str
) -> dict:
    """Re-validates the (possibly user-edited) column mapping, then loops each
    row through the target table's own create-service function. One bad row
    never aborts the whole import — it's recorded in `skipped` with a reason."""
    session = db.get(ImportSession, import_session_id)
    if session is None:
        raise ImportSessionNotFound(f"import session '{import_session_id}' not found")

    required = REQUIRED_FIELDS[session.target_table]
    mapped_fields = {field for field in column_mapping.values() if field}
    missing = required - mapped_fields
    if missing:
        raise ValueError(f"missing required field mapping(s): {sorted(missing)}")

    builder = _ROW_BUILDERS[session.target_table]
    imported = 0
    skipped: list[dict] = []
    for i, raw_row in enumerate(session.raw_rows):
        mapped_row = {
            field: raw_row.get(source_col)
            for source_col, field in column_mapping.items()
            if field and source_col in raw_row
        }
        try:
            builder(db, hospital_id=session.hospital_id, row=mapped_row, actor=actor)
            imported += 1
        except ValueError as exc:
            skipped.append({"row": i, "reason": str(exc)})

    return {"imported": imported, "skipped": skipped}


def discard_session(db: Session, import_session_id: str) -> None:
    session = db.get(ImportSession, import_session_id)
    if session is None:
        raise ImportSessionNotFound(f"import session '{import_session_id}' not found")
    db.delete(session)
    db.commit()
