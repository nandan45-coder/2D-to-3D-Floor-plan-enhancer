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
    Create all tables registered on Base.metadata.

    This is an MVP convenience (no migration tool wired up yet). If/when
    Alembic or another migration tool is introduced, this call should be
    replaced by running migrations instead.
    """
    from app import models  # noqa: F401  -- ensures models are registered on Base.metadata

    Base.metadata.create_all(bind=engine)
