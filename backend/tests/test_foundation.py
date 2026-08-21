"""
Foundation smoke tests (Prompt 2).

Uses the shared test database/client fixtures from conftest.py -- see that
file's docstring for why per-file database setup was replaced with a single
shared fixture (Prompt 7 fixed a cross-file test-isolation bug here).
"""


def test_root_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "running"


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_create_and_list_project(client):
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


def test_get_project_by_id(client):
    create_resp = client.post("/projects", json={"name": "Studio Apartment"})
    project_id = create_resp.json()["id"]

    get_resp = client.get(f"/projects/{project_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == project_id


def test_get_project_not_found_returns_consistent_error_format(client):
    resp = client.get("/projects/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "message" in body["error"]


def test_create_project_validation_error_format(client):
    resp = client.post("/projects", json={"description": "missing required name"})
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_update_and_delete_project(client):
    create_resp = client.post("/projects", json={"name": "To Update"})
    project_id = create_resp.json()["id"]

    update_resp = client.patch(f"/projects/{project_id}", json={"name": "Updated Name"})
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Name"

    delete_resp = client.delete(f"/projects/{project_id}")
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/projects/{project_id}")
    assert get_resp.status_code == 404
