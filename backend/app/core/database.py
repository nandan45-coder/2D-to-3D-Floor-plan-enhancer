"""
Database engine and session setup.

Any backend module needing DB access should depend on `get_db` (a FastAPI
dependency yielding a scoped Session) rather than importing SessionLocal
directly. `Base` is the declarative base every SQLAlchemy model must inherit
from -- this keeps a single shared metadata registry across the whole app.
"""
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# SQLite needs a special connect arg to allow use across FastAPI's threaded
# request handling. Postgres (the target production DB) does not need this.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Context manager for DB sessions used outside of request handling."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_database_connection() -> bool:
    """
    Lightweight connectivity check used by GET /health.
    Returns True if a trivial query succeeds, False otherwise.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 -- health check must never raise
        logger.error("Database connectivity check failed: %s", exc)
        return False


def init_db() -> None:
    """
    Bring the database schema up to date by running the Alembic migrations (UI-2; backend/migrations/versions).
    Works for a fresh database and for one created before Alembic (the baseline creates only missing tables).
    """
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    from app import models  # noqa: F401  -- ensures models are registered on Base.metadata

    root = Path(__file__).resolve().parents[2]          # the backend folder
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    cfg.attributes["skip_logging"] = True               # keep the app's logging configuration
    with engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
