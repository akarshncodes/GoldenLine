"""FR-22 Rule-Based Fuzzy Import.

Acceptance criteria:
  * column matching is deterministic string similarity (difflib), never ML,
    and never auto-commits below the confidence cutoff;
  * the two-step preview/confirm flow never writes real data until commit,
    and commit reuses each target table's own create-service function so
    validation isn't duplicated;
  * one bad row never aborts the whole import.
"""
import io

from app.services.import_matching import suggest_column_mapping


# --------------------------------------------------------- pure matching unit tests
def test_exact_field_name_matches():
    res = suggest_column_mapping(["full_name", "approx_age"], "patients")
    assert res[0] == {"source_column": "full_name", "matched_field": "full_name", "confidence": 1.0}
    assert res[1]["matched_field"] == "approx_age"


def test_synonym_matches():
    res = suggest_column_mapping(["Name", "Age", "Phone"], "patients")
    fields = {r["source_column"]: r["matched_field"] for r in res}
    assert fields["Name"] == "full_name"
    assert fields["Age"] == "approx_age"
    assert fields["Phone"] == "phone_number"


def test_typo_still_matches_above_cutoff():
    res = suggest_column_mapping(["Pateint Name"], "patients")  # deliberate typo
    assert res[0]["matched_field"] == "full_name"
    assert res[0]["confidence"] >= 0.6


def test_unrelated_column_is_unmatched():
    res = suggest_column_mapping(["Favourite Colour"], "patients")
    assert res[0]["matched_field"] is None
    assert res[0]["confidence"] == 0.0


def test_unknown_target_table_raises():
    try:
        suggest_column_mapping(["x"], "not_a_real_table")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_each_target_table_has_working_aliases():
    cases = {
        "hospital_staff": (["Doctor Name", "Role"], {"full_name", "staff_category"}),
        "hospital_inventory_items": (["Item", "Qty"], {"item_name", "quantity_on_hand"}),
        "bed_categories": (["Room Type", "Capacity"], {"label", "total_beds"}),
    }
    for table, (headers, expected_fields) in cases.items():
        res = suggest_column_mapping(headers, table)
        matched = {r["matched_field"] for r in res}
        assert expected_fields.issubset(matched), f"{table}: {res}"


# --------------------------------------------------------------- preview + commit (API)
_PATIENTS_CSV = (
    "Name,Age,Gender,Phone\r\n"
    "Ravi Kumar,45,male,9123456789\r\n"
    "Asha Devi,60,female,\r\n"
    ",30,male,9988776655\r\n"  # bad row: missing name
)


def test_preview_file_returns_match_report(client):
    files = {"file": ("patients.csv", io.BytesIO(_PATIENTS_CSV.encode()), "text/csv")}
    res = client.post(
        "/hospitals/HOSP-001/import/preview-file",
        data={"target_table": "patients"},
        files=files,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["target_table"] == "patients"
    assert body["row_count"] == 3
    cols = {c["source_column"]: c for c in body["columns"]}
    assert cols["Name"]["matched_field"] == "full_name"
    assert cols["Age"]["matched_field"] == "approx_age"
    assert cols["Name"]["sample_values"][0] == "Ravi Kumar"
    assert body["unmatched_columns"] == []


def _preview(client, hospital_id="HOSP-001", target_table="patients", csv_text=_PATIENTS_CSV):
    files = {"file": ("data.csv", io.BytesIO(csv_text.encode()), "text/csv")}
    res = client.post(
        f"/hospitals/{hospital_id}/import/preview-file", data={"target_table": target_table}, files=files
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_commit_imports_valid_rows_and_skips_bad_ones(client):
    report = _preview(client)
    mapping = {c["source_column"]: c["matched_field"] for c in report["columns"]}

    res = client.post(
        f"/hospitals/HOSP-001/import/{report['import_session_id']}/commit",
        json={"column_mapping": mapping},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["imported"] == 2  # 2 valid rows
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["row"] == 2
    assert "full_name" in body["skipped"][0]["reason"]

    census = client.get("/hospitals/HOSP-001/patients").json()
    names = {p["full_name"] for p in census}
    assert {"Ravi Kumar", "Asha Devi"}.issubset(names)


def test_commit_missing_required_mapping_400s(client):
    report = _preview(client)
    # drop the full_name mapping entirely -> required field unmapped
    mapping = {c["source_column"]: None for c in report["columns"]}
    res = client.post(
        f"/hospitals/HOSP-001/import/{report['import_session_id']}/commit",
        json={"column_mapping": mapping},
    )
    assert res.status_code == 400


def test_user_can_override_a_suggested_mapping(client):
    csv_text = "Col1,Col2\r\nSome Name,99\r\n"  # headers with no aliases at all
    report = _preview(client, csv_text=csv_text)
    assert all(c["matched_field"] is None for c in report["columns"])

    # user manually maps Col1 -> full_name, ignores Col2
    mapping = {"Col1": "full_name", "Col2": None}
    res = client.post(
        f"/hospitals/HOSP-001/import/{report['import_session_id']}/commit",
        json={"column_mapping": mapping},
    )
    assert res.status_code == 200, res.text
    assert res.json()["imported"] == 1


def test_discard_removes_the_session(client):
    report = _preview(client)
    sid = report["import_session_id"]
    res = client.delete(f"/hospitals/HOSP-001/import/{sid}")
    assert res.status_code == 200
    assert client.get(f"/hospitals/HOSP-001/import/{sid}").status_code == 404


def test_unknown_session_404s(client):
    assert client.get("/hospitals/HOSP-001/import/does-not-exist").status_code == 404
    assert client.delete("/hospitals/HOSP-001/import/does-not-exist").status_code == 404


def test_receptionist_scoped_to_own_hospital(client_factory):
    recep1 = client_factory("recep-hosp-001")
    recep4 = client_factory("recep-hosp-004")

    files = {"file": ("p.csv", io.BytesIO(_PATIENTS_CSV.encode()), "text/csv")}
    ok = recep1.post("/hospitals/HOSP-001/import/preview-file", data={"target_table": "patients"}, files=files)
    assert ok.status_code == 200

    files2 = {"file": ("p.csv", io.BytesIO(_PATIENTS_CSV.encode()), "text/csv")}
    forbidden = recep4.post(
        "/hospitals/HOSP-001/import/preview-file", data={"target_table": "patients"}, files=files2
    )
    assert forbidden.status_code == 403

    sid = ok.json()["import_session_id"]
    assert recep4.get(f"/hospitals/HOSP-001/import/{sid}").status_code == 403


def test_google_sheet_preview_real_export_path(client, monkeypatch):
    """Mirrors test_fr16_hospital_sync.py's Google-Sheets mocking style."""
    import app.services.hospital_import as hi

    real_id = "1" + "A" * 43  # realistic 44-char id
    captured = {}

    class _Resp:
        text = "Item,Category,Unit,Qty\r\nGloves,ppe,box,10\r\n"

        def raise_for_status(self):
            pass

    def fake_get(url, **kw):
        captured["url"] = url
        return _Resp()

    monkeypatch.setattr(hi.httpx, "get", fake_get)
    res = client.post(
        "/hospitals/HOSP-001/import/preview-sheet",
        json={
            "sheet_url": f"https://docs.google.com/spreadsheets/d/{real_id}/edit",
            "target_table": "hospital_inventory_items",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["row_count"] == 1
    assert captured["url"] == f"https://docs.google.com/spreadsheets/d/{real_id}/export?format=csv"
    cols = {c["source_column"]: c["matched_field"] for c in body["columns"]}
    assert cols["Item"] == "item_name"
    assert cols["Qty"] == "quantity_on_hand"


def test_non_google_sheet_url_400s(client):
    res = client.post(
        "/hospitals/HOSP-001/import/preview-sheet",
        json={"sheet_url": "https://example.com/not-a-sheet", "target_table": "patients"},
    )
    assert res.status_code == 400


def test_staff_attendance_is_not_a_valid_target_table(client):
    files = {"file": ("x.csv", io.BytesIO(b"a,b\r\n1,2\r\n"), "text/csv")}
    res = client.post(
        "/hospitals/HOSP-001/import/preview-file", data={"target_table": "staff_attendance"}, files=files
    )
    assert res.status_code == 400
