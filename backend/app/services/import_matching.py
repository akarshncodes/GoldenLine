"""FR-22 rule-based fuzzy column matching — pure, DB-free, unit-testable alone.

Deterministic string similarity (stdlib `difflib`) against a known alias
dictionary per target table. Zero ML — matches the project's "explainable, no
ML" design philosophy already used elsewhere (e.g. FR-2's specialty lookup).
Below the confidence cutoff a column is left unmatched and must be resolved
manually before commit — nothing is ever auto-committed past the threshold.
"""
import difflib

# The four FR-17/18/19/21 tables this import can populate. FR-20 (staff
# attendance) is deliberately excluded — a live clock-in/out feed isn't
# sensibly bulk-imported from a static HMS export.
TARGET_TABLES = ("patients", "hospital_staff", "hospital_inventory_items", "bed_categories")

REQUIRED_FIELDS: dict[str, set[str]] = {
    "patients": {"full_name"},
    "hospital_staff": {"full_name", "staff_category"},
    "hospital_inventory_items": {"item_name", "category", "unit"},
    "bed_categories": {"category_code", "label", "total_beds"},
}

TARGET_FIELD_ALIASES: dict[str, dict[str, set[str]]] = {
    "patients": {
        "full_name": {"name", "patient name", "pt name", "full name", "patient_name"},
        "approx_age": {"age", "patient age", "years"},
        "gender": {"gender", "sex"},
        "phone_number": {"phone", "phone number", "contact", "mobile", "contact number"},
        "patient_type": {"type", "patient type", "admission type"},
    },
    "hospital_staff": {
        "full_name": {"name", "staff name", "full name", "doctor name"},
        "staff_category": {"category", "role", "designation", "staff type"},
        "specialty": {"specialty", "speciality", "department"},
        "phone_number": {"phone", "contact", "mobile", "phone number"},
    },
    "hospital_inventory_items": {
        "item_name": {"name", "item", "item name", "product name"},
        "category": {"category", "type"},
        "unit": {"unit", "uom", "units"},
        "quantity_on_hand": {"quantity", "qty", "stock", "count", "on hand"},
        "low_stock_threshold": {"threshold", "reorder level", "min stock", "low stock alert"},
    },
    "bed_categories": {
        "category_code": {"code", "category code"},
        "label": {"label", "name", "category name", "room type"},
        "total_beds": {"beds", "total beds", "capacity", "count"},
    },
}

_CUTOFF = 0.6


def suggest_column_mapping(headers: list[str], target_table: str) -> list[dict]:
    """One entry per header, in the order given:
    `{"source_column": str, "matched_field": str | None, "confidence": float}`.
    `matched_field` is None (never guessed) below the confidence cutoff."""
    field_aliases = TARGET_FIELD_ALIASES.get(target_table)
    if field_aliases is None:
        raise ValueError(f"unknown target_table '{target_table}'")

    alias_to_field: dict[str, str] = {}
    for field, aliases in field_aliases.items():
        alias_to_field[field] = field  # the field's own name is always a valid alias
        for alias in aliases:
            alias_to_field[alias] = field
    pool = list(alias_to_field.keys())

    results = []
    for header in headers:
        norm = (header or "").strip().lower()
        matches = difflib.get_close_matches(norm, pool, n=1, cutoff=_CUTOFF)
        if matches:
            best = matches[0]
            confidence = round(difflib.SequenceMatcher(None, norm, best).ratio(), 2)
            results.append({"source_column": header, "matched_field": alias_to_field[best], "confidence": confidence})
        else:
            results.append({"source_column": header, "matched_field": None, "confidence": 0.0})
    return results
