"""
Shared pytest fixtures for all API-level tests.

Why this file exists: `app.dependency_overrides[get_db]` is a single dict
entry on the process-wide FastAPI `app` singleton. Before this file
existed, test_foundation.py and test_detection_api.py each defined their
OWN separate SQLite engine and independently assigned
`app.dependency_overrides[get_db] = <their own override>` at module level.
Since pytest imports (collects) every test module before running any test,
whichever file happened to import LAST silently won that override for
EVERY test file's tests -- including files whose own database tables were
never created, because table creation lived in a per-file fixture that
hadn't run yet. This surfaced as "no such table: projects" failures that
only appeared when the full suite ran together, never when a single test
file ran in isolation.

Fix: one shared engine, one shared override, defined ONCE here. Every test
file that needs the API (TestClient) should use the `client` fixture below
instead of constructing its own.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_shared.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test_shared.db"
_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
_TestingSessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def _override_get_db():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="session", autouse=True)
def _setup_shared_test_database():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)
    if os.path.exists("test_shared.db"):
        os.remove("test_shared.db")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
