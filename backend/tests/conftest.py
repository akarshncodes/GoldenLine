"""Test fixtures: a fresh SQLite database per test, with get_db overridden.

FR-11: every endpoint now needs auth, so `client` is authenticated as `admin`
(admin bypasses role scoping — existing behaviour is unchanged). Role-scoped
tests use `client_as(user_id)` or the per-role fixtures.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registers models on Base.metadata)
from app.database import Base, apply_sqlite_pragmas, get_db
from app.main import app
from app.services import ratelimit
from app.services.hospital_seed import seed_hospitals
from app.services.reference_seed import seed_reference
from app.services.security import mint_token
from app.services.user_seed import seed_users


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture(autouse=True)
def _no_osrm_network(monkeypatch):
    """Keep the suite hermetic: no real network calls to the public OSRM service.

    app/services/maps.py falls back to OSRM whenever no Google Maps key is set
    (true in every test), so without this the whole suite would hit the real
    internet. Tests that specifically want to exercise the OSRM tier re-enable
    it and mock httpx.get themselves (see test_fr4_route.py).
    """
    from app.config import get_settings

    monkeypatch.setenv("OSRM_ROUTING_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def _db_setup(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    apply_sqlite_pragmas(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    with TestingSessionLocal() as seed_db:
        seed_hospitals(seed_db)
        seed_reference(seed_db)
        seed_users(seed_db)
    try:
        yield engine, TestingSessionLocal
    finally:
        engine.dispose()


def _token_for(session_local, user_id: str) -> str:
    from app.models.auth import User

    with session_local() as db:
        user = db.get(User, user_id)
        assert user is not None, f"seed user {user_id!r} missing"
        return mint_token(
            user_id=user.user_id, role=user.role.value, hospital_id=user.hospital_id,
            blood_bank_id=user.blood_bank_id, phone_number=user.phone_number,
        )


@pytest.fixture()
def client(_db_setup):
    _engine, TestingSessionLocal = _db_setup

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = f"Bearer {_token_for(TestingSessionLocal, 'admin')}"
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def client_factory(_db_setup):
    """client_factory('recep-hosp-001') -> a TestClient authed as that seeded user."""
    _engine, TestingSessionLocal = _db_setup

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    made: list[TestClient] = []

    def _make(user_id: str | None) -> TestClient:
        c = TestClient(app)
        c.__enter__()
        if user_id is not None:
            c.headers["Authorization"] = f"Bearer {_token_for(TestingSessionLocal, user_id)}"
        made.append(c)
        return c

    yield _make
    for c in made:
        c.__exit__(None, None, None)
    app.dependency_overrides.clear()


@pytest.fixture()
def db_session(_db_setup):
    _engine, TestingSessionLocal = _db_setup
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
