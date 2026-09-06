"""Guard: migration 0006's inline seed is frozen historical DDL (the original
10 fake hospitals) — it must never be edited to match the live seed module.
Migration 0024 replaces its rows entirely with real Dindigul hospitals; see
test_fr4_fr5_seed_parity.py::test_migration_0024_hospitals_match_seed_module.
"""
import importlib.util
from pathlib import Path

_MIG = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0006_fr2_hospitals.py"


def _load_migration_seed():
    spec = importlib.util.spec_from_file_location("mig_0006", _MIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._SEED


def test_migration_0006_is_the_frozen_original_ten_fake_hospitals():
    mig = _load_migration_seed()
    assert len(mig) == 10
    by_id = {r[0]: r for r in mig}
    assert by_id["HOSP-001"][1:3] == (
        "City Government Hospital",
        ["emergency", "cardiology", "pulmonology", "neurology", "general_medicine", "trauma_surgery", "obstetrics"],
    )
    assert by_id["HOSP-001"][8] == "Government-Low"
