"""End-to-end guard: run the REAL migration chain (not the ORM create_all()
path every other test uses) against a fresh SQLite file, then verify every
documented demo account can actually log in with its documented
`<user_id>.sih2026` password.

This is the test that would have caught the 2026-09-05 bug where HLP-001/002
(renamed from ATT-9/ATT-1 by migration 0023) kept their OLD pre-rename
password hash — a hash-function-only unit test doesn't exercise the actual
migration-produced database, so it missed that migration 0023 forgot to
re-hash the two renamed rows (it only hashed the brand-new ones it inserted).
Every seeded account's login is checked here so a future rename/migration
bug like this can't slip through again.
"""
import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_every_seeded_account_can_log_in_after_a_real_migration_run(tmp_path, monkeypatch):
    backend_dir = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from app.config import get_settings

    get_settings.cache_clear()
    try:
        cfg = Config(str(backend_dir / "alembic.ini"))
        cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        command.upgrade(cfg, "head")

        from app.services.security import verify_password
        from app.services.user_seed import SEED_USERS, dev_password

        conn = sqlite3.connect(db_path)
        try:
            rows = {
                r[0]: r[1]
                for r in conn.execute("SELECT user_id, password_hash FROM users")
            }
        finally:
            conn.close()

        checked = 0
        for u in SEED_USERS:
            uid = u["user_id"]
            assert uid in rows, f"seeded account {uid!r} missing from the migrated DB"
            password_hash = rows[uid]
            assert password_hash is not None, f"{uid!r} has no password_hash after migrating"
            assert verify_password(dev_password(uid), password_hash), (
                f"{uid!r} can't log in with its documented password "
                f"{dev_password(uid)!r} after a real migration run"
            )
            checked += 1
        assert checked == len(SEED_USERS)
    finally:
        get_settings.cache_clear()
