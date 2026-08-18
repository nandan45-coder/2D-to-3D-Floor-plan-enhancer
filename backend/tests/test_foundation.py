"""
Foundation smoke tests (Prompt 2).

Uses a temporary SQLite database (via dependency override) so tests are
self-contained and don't require a running PostgreSQL instance.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_foundation.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test_foundation.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test_foundation.db"):
        os.remove("test_foundation.db")


client = TestClient(app)


def test_root_ok():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_create_and_list_project():
    create_resp = client.post("/projects", json={"name": "Sample House", "description": "Test project"})
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["name"] == "Sample House"
    assert created["status"] == "created"
    assert "id" in created

    list_resp = client.get("/projects")
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert any(p["id"] == created["id"] for p in projects)


def test_get_project_by_id():
    create_resp = client.post("/projects", json={"name": "Studio Apartment"})
    project_id = create_resp.json()["id"]

    get_resp = client.get(f"/projects/{project_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == project_id


def test_get_project_not_found_returns_consistent_error_format():
    resp = client.get("/projects/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "message" in body["error"]


def test_create_project_validation_error_format():
    resp = client.post("/projects", json={"description": "missing required name"})
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_update_and_delete_project():
    create_resp = client.post("/projects", json={"name": "To Update"})
    project_id = create_resp.json()["id"]

    update_resp = client.patch(f"/projects/{project_id}", json={"name": "Updated Name"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Name"

    delete_resp = client.delete(f"/projects/{project_id}")
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/projects/{project_id}")
    assert get_resp.status_code == 404
