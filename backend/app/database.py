"""Database engine, session factory, and declarative base."""
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")
# check_same_thread is a SQLite-only flag; ignored for PostgreSQL.
connect_args = {"check_same_thread": False} if _is_sqlite else {}


def apply_sqlite_pragmas(target_engine: Engine) -> None:
    """Wait on a busy DB instead of erroring immediately — needed so concurrent
    bed-lock attempts (FR-3) serialize on SQLite's write lock rather than failing
    with 'database is locked'. No-op for non-SQLite engines."""
    if target_engine.dialect.name != "sqlite":
        return

    @event.listens_for(target_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record):  # pragma: no cover - trivial
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout = 5000")
        cursor.close()


engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)
apply_sqlite_pragmas(engine)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Base class for all ORM models."""


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
