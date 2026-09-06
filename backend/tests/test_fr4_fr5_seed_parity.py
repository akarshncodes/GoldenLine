"""Guard: migration inline seeds match the seed modules."""
import importlib.util
from pathlib import Path

from app.services.hospital_seed import SEED_HOSPITALS
from app.services.reference_seed import SEED_BLOOD_BANKS, SEED_WAYPOINTS

_VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _VERSIONS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_migration_0008_is_the_frozen_original_hospital_extras():
    """0008 is historical DDL for the original 10 fake hospitals — frozen
    forever. Migration 0024 replaces all of it (lat/long/blood stock included)
    with real Dindigul data; see test_migration_0024_hospitals_match_seed_module.
    """
    extras = _load("0008_fr4_fr5_columns")._HOSPITAL_EXTRAS
    assert set(extras) == {f"HOSP-{i:03d}" for i in range(1, 11)}
    assert extras["HOSP-001"] == (12.9784, 77.5920, {"O-": 1, "O+": 6, "A+": 4, "B+": 3, "AB+": 1})


def test_migration_0009_is_the_frozen_original_bengaluru_waypoints():
    """0009 is historical DDL — frozen forever. Migration 0025 relabels all 5
    rows (same ids) to real Dindigul localities; see
    test_migration_0025_waypoints_match_seed_module.
    """
    rows = _load("0009_fr4_route_tables")._WAYPOINTS
    by_id = {r[0]: r for r in rows}
    assert set(by_id) == {"WP-01", "WP-02", "WP-03", "WP-04", "WP-05"}
    assert by_id["WP-01"][1:3] == ("Jayanagar PHC", "PHC")


def test_migration_0025_waypoints_match_seed_module():
    rows = _load("0025_dindigul_waypoints")._WAYPOINTS
    by_id = {r[0]: r for r in rows}
    assert set(by_id) == {w["waypoint_id"] for w in SEED_WAYPOINTS}
    for w in SEED_WAYPOINTS:
        r = by_id[w["waypoint_id"]]
        assert r[1:] == (
            w["name"], w["kind"], w["latitude"], w["longitude"], w["has_oxygen"], w["has_doctor"],
        )


def test_migration_0010_is_the_frozen_original_three_fake_blood_banks():
    """0010 is historical DDL — frozen forever. Migration 0024 overwrites all
    3 rows' content with the real Dindigul blood banks (same 3 ids); see
    test_migration_0024_blood_banks_match_seed_module.
    """
    rows = _load("0010_fr5_blood_tables")._BLOOD_BANKS
    by_id = {r[0]: r for r in rows}
    assert set(by_id) == {"BB-01", "BB-02", "BB-03"}
    assert by_id["BB-01"][1] == "Central Blood Bank"


def test_migration_0019_is_the_frozen_original_sync_tiers():
    """0019 is historical DDL for the original 10 fake hospitals — frozen
    forever. Migration 0024 sets the sync tier for all 25 real hospitals
    directly as part of its fresh insert; see
    test_migration_0024_hospitals_match_seed_module.
    """
    tiers = _load("0019_fr16_hospital_sync")._SYNC_TIERS
    assert set(tiers) == {f"HOSP-{i:03d}" for i in range(1, 11)}
    assert tiers["HOSP-001"] == "hms_api"
    assert tiers["HOSP-007"] == "manual_counter"
    assert set(tiers.values()) == {"hms_api", "google_sheets", "manual_counter"}


def test_migration_0024_hospitals_match_seed_module():
    """0024's fresh insert (25 real Dindigul hospitals, sync tier included)
    must equal the live `hospital_seed.SEED_HOSPITALS` truth exactly."""
    from app.services.hospital_sync import SEED_SYNC_TIERS

    rows = _load("0024_dindigul_real_data")._HOSPITALS
    by_id = {r[0]: r for r in rows}
    assert set(by_id) == {h["hospital_id"] for h in SEED_HOSPITALS} == set(SEED_SYNC_TIERS)
    for h in SEED_HOSPITALS:
        r = by_id[h["hospital_id"]]
        assert r[1] == h["name"]
        assert r[2] == h["specialties"]
        assert (r[3], r[4], r[5], r[6], r[7]) == (
            h["live_bed_count"], h["live_icu_count"], h["distance_km"],
            h["eta_minutes"], h["rating"],
        )
        assert r[8] == h["cost_tier"]
        assert r[9] == h["accepted_schemes"]
        assert (r[10], r[11]) == (h["latitude"], h["longitude"])
        assert r[12] == h["blood_stock_by_group"]
        assert r[13] == h["hospital_sync_tier"] == SEED_SYNC_TIERS[h["hospital_id"]]


def test_migration_0024_blood_banks_match_seed_module():
    rows = _load("0024_dindigul_real_data")._BLOOD_BANKS
    by_id = {r[0]: r for r in rows}
    assert set(by_id) == {b["blood_bank_id"] for b in SEED_BLOOD_BANKS}
    for b in SEED_BLOOD_BANKS:
        r = by_id[b["blood_bank_id"]]
        assert r[1:] == (
            b["name"], b["latitude"], b["longitude"],
            b["linked_hospital_ids"], b["stock_by_group"],
        )


def test_migration_0016_users_are_the_frozen_historical_seed():
    """Migration 0016 is historical DDL and must never be edited — it stays
    pinned to its original ('attender'-named) shape forever. Migration 0023
    renames it to the current truth; see test_migration_0023_renames_users_to_match_seed.
    """
    rows = _load("0016_fr11_fr12_security")._USERS
    by_id = {r[0]: r for r in rows}
    assert set(by_id) == {
        "admin", "control-room", "ATT-9", "ATT-1",
        "recep-hosp-001", "recep-hosp-004", "recep-hosp-007",
        "coord-bb-01", "coord-bb-02",
    }
    assert by_id["ATT-9"][1:3] == ("attender", "Attender Ravi")
    assert by_id["ATT-1"][1:3] == ("attender", "Attender Suresh")


def test_migrations_0016_0023_0024_together_produce_the_live_seed():
    """0016's original 9 users, after 0023's attender->helper rename (+3 new
    helpers) and then 0024's Dindigul rename (+15 more helpers, +coord-bb-03,
    receptionist/coordinator display-name updates), must equal the live
    `user_seed.SEED_USERS` truth exactly."""
    from app.services.user_seed import SEED_USERS

    rows = _load("0016_fr11_fr12_security")._USERS
    by_id = {r[0]: list(r) for r in rows}

    rename = {"ATT-9": ("HLP-001", "Helper Ravi"), "ATT-1": ("HLP-002", "Helper Suresh")}
    migrated = {}
    for old_id, row in by_id.items():
        new_id, new_name = rename.get(old_id, (old_id, row[2]))
        role = "helper" if row[1] == "attender" else row[1]
        migrated[new_id] = {
            "user_id": new_id, "role": role, "display_name": new_name,
            "phone_number": row[3], "hospital_id": row[4], "blood_bank_id": row[5],
        }

    m0023 = _load("0023_attender_to_helper_rename")
    for uid, name, phone in m0023._NEW_HELPERS:
        migrated[uid] = {
            "user_id": uid, "role": "helper", "display_name": name,
            "phone_number": phone, "hospital_id": None, "blood_bank_id": None,
        }

    m0024 = _load("0024_dindigul_real_data")
    for hlp_id, (name, phone) in m0024._HELPER_RENAMES.items():
        migrated[hlp_id]["display_name"] = name
        migrated[hlp_id]["phone_number"] = phone
    for uid, name, phone in m0024._NEW_HELPERS:
        migrated[uid] = {
            "user_id": uid, "role": "helper", "display_name": name,
            "phone_number": phone, "hospital_id": None, "blood_bank_id": None,
        }
    for user_id, name in m0024._RECEPTIONIST_RENAMES.items():
        migrated[user_id]["display_name"] = name
    for user_id, name in m0024._COORDINATOR_RENAMES.items():
        migrated[user_id]["display_name"] = name
    migrated["coord-bb-03"] = {
        "user_id": "coord-bb-03", "role": "blood_bank_coordinator",
        "display_name": "Coordinator — Indian Blood",
        "phone_number": None, "hospital_id": None, "blood_bank_id": "BB-03",
    }

    assert set(migrated) == {u["user_id"] for u in SEED_USERS}
    for u in SEED_USERS:
        got = migrated[u["user_id"]]
        assert got["role"] == u["role"]
        assert got["display_name"] == u["display_name"]
        assert got["phone_number"] == u.get("phone_number")
        assert got["hospital_id"] == u.get("hospital_id")
        assert got["blood_bank_id"] == u.get("blood_bank_id")


def test_migration_0020_password_backfill_matches_its_own_seed_id_list():
    """The 0020 backfill must produce hashes `security.verify_password` accepts
    for the dev password `user_seed.dev_password` computes — checked against
    0020's own (historical, 'attender'-named) id list, not the live seed."""
    from app.services.security import verify_password
    from app.services.user_seed import dev_password

    mod = _load("0020_fr11_user_passwords")
    assert set(mod._SEED_USER_IDS) == {
        "admin", "control-room", "ATT-9", "ATT-1",
        "recep-hosp-001", "recep-hosp-004", "recep-hosp-007",
        "coord-bb-01", "coord-bb-02",
    }
    assert mod._DEV_PASSWORD_SUFFIX == "sih2026"
    for uid in mod._SEED_USER_IDS:
        encoded = mod._hash(dev_password(uid))
        assert encoded.startswith("pbkdf2_sha256$")
        assert dev_password(uid) not in encoded
        assert verify_password(dev_password(uid), encoded)


def test_migration_0023_new_helper_passwords_match_app_hashing():
    from app.services.security import verify_password
    from app.services.user_seed import dev_password

    mod = _load("0023_attender_to_helper_rename")
    for uid, _name, _phone in mod._NEW_HELPERS:
        encoded = mod._hash(dev_password(uid))
        assert encoded.startswith("pbkdf2_sha256$")
        assert verify_password(dev_password(uid), encoded)


def test_migration_0024_new_helper_and_coordinator_passwords_match_app_hashing():
    from app.services.security import verify_password
    from app.services.user_seed import dev_password

    mod = _load("0024_dindigul_real_data")
    for uid, _name, _phone in mod._NEW_HELPERS:
        encoded = mod._hash(dev_password(uid))
        assert encoded.startswith("pbkdf2_sha256$")
        assert verify_password(dev_password(uid), encoded)
    encoded = mod._hash(dev_password("coord-bb-03"))
    assert verify_password(dev_password("coord-bb-03"), encoded)
