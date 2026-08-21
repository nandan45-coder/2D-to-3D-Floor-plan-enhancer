"""
Detection API route tests (Prompt 7).

Uses the shared test database/client fixtures from conftest.py -- see that
file's docstring for why per-file database setup was replaced with a single
shared fixture (this was the second file to independently override
app.dependency_overrides[get_db], which is what surfaced the cross-file
test-isolation bug conftest.py fixes).

Uploads the real synthetic sample images generated for Prompt 6, so this
exercises the actual detection pipeline end-to-end through the HTTP layer,
not a mocked version of it.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "data" / "samples"
COTTAGE_PATH = SAMPLES_DIR / "sample_floorplan_cottage.png"


@pytest.fixture(autouse=True)
def isolated_storage_path(tmp_path, monkeypatch):
    """Redirect uploaded-file storage to a temp dir so tests don't pollute backend/data/uploads."""
    from app.services import storage_service
    monkeypatch.setattr(storage_service.settings, "storage_path", str(tmp_path))
    yield


def _create_project(client, name: str = "Detection Test Project") -> str:
    resp = client.post("/projects", json={"name": name})
    assert resp.status_code == 201
    return resp.json()["id"]


# --- Status endpoint ---------------------------------------------------------


def test_status_defaults_to_not_started(client):
    project_id = _create_project(client)
    resp = client.get(f"/projects/{project_id}/floorplan/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "not_started"
    assert body["error"] is None


def test_status_for_nonexistent_project_is_404(client):
    resp = client.get("/projects/does-not-exist/floorplan/status")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# --- Result endpoint (before upload) -------------------------------------------


def test_result_before_upload_is_409_conflict(client):
    project_id = _create_project(client)
    resp = client.get(f"/projects/{project_id}/floorplan/result")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "CONFLICT"


# --- Upload + detect (happy path) ----------------------------------------------


def test_upload_and_detect_cottage_end_to_end(client):
    project_id = _create_project(client)

    with open(COTTAGE_PATH, "rb") as f:
        resp = client.post(
            f"/projects/{project_id}/floorplan/upload",
            files={"file": ("sample_floorplan_cottage.png", f, "image/png")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["error"] is None
    assert body["summary"]["room_count"] == 2
    assert body["summary"]["wall_count"] == 5
    assert body["summary"]["door_count"] == 2
    assert body["summary"]["window_count"] == 1
    assert body["summary"]["stair_count"] == 1


def test_status_reflects_complete_after_upload(client):
    project_id = _create_project(client)
    with open(COTTAGE_PATH, "rb") as f:
        client.post(
            f"/projects/{project_id}/floorplan/upload",
            files={"file": ("sample_floorplan_cottage.png", f, "image/png")},
        )

    resp = client.get(f"/projects/{project_id}/floorplan/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "complete"


def test_result_available_and_schema_valid_after_upload(client):
    from app.floorplan.validator import validate_floorplan

    project_id = _create_project(client)
    with open(COTTAGE_PATH, "rb") as f:
        client.post(
            f"/projects/{project_id}/floorplan/upload",
            files={"file": ("sample_floorplan_cottage.png", f, "image/png")},
        )

    resp = client.get(f"/projects/{project_id}/floorplan/result")
    assert resp.status_code == 200
    floorplan_dict = resp.json()

    result = validate_floorplan(floorplan_dict)
    assert result.is_valid, result.errors
    assert floorplan_dict["project_id"] == project_id


def test_result_persists_across_requests(client):
    """Confirms the FloorPlan is actually persisted to the DB, not just held in memory from the upload response."""
    project_id = _create_project(client)
    with open(COTTAGE_PATH, "rb") as f:
        client.post(
            f"/projects/{project_id}/floorplan/upload",
            files={"file": ("sample_floorplan_cottage.png", f, "image/png")},
        )

    first = client.get(f"/projects/{project_id}/floorplan/result").json()
    second = client.get(f"/projects/{project_id}/floorplan/result").json()
    assert first == second


# --- Upload error paths ---------------------------------------------------------


def test_upload_unsupported_file_type_is_415(client):
    project_id = _create_project(client)
    resp = client.post(
        f"/projects/{project_id}/floorplan/upload",
        files={"file": ("not_a_floorplan.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_oversized_file_is_413(client):
    from app.cv.preprocessing import MAX_UPLOAD_BYTES

    project_id = _create_project(client)
    oversized_content = b"\x00" * (MAX_UPLOAD_BYTES + 1024)
    resp = client.post(
        f"/projects/{project_id}/floorplan/upload",
        files={"file": ("too_big.png", oversized_content, "image/png")},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_upload_to_nonexistent_project_is_404(client):
    resp = client.post(
        "/projects/does-not-exist/floorplan/upload",
        files={"file": ("sample.png", b"fake", "image/png")},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_upload_status_after_failed_detection(client):
    """
    A validly-typed file that isn't actually a real image (garbage bytes)
    should be accepted at the upload/storage layer (it passes the extension
    check) but fail during detection -- the endpoint should report
    status="failed" with a 200, not crash with a 500.
    """
    project_id = _create_project(client)
    resp = client.post(
        f"/projects/{project_id}/floorplan/upload",
        files={"file": ("corrupt.png", b"not actually a png", "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error"] is not None

    status_resp = client.get(f"/projects/{project_id}/floorplan/status")
    assert status_resp.json()["status"] == "failed"
    assert status_resp.json()["error"] is not None


def test_studio_sample_also_works_end_to_end(client):
    studio_path = SAMPLES_DIR / "sample_floorplan_studio.png"
    project_id = _create_project(client)
    with open(studio_path, "rb") as f:
        resp = client.post(
            f"/projects/{project_id}/floorplan/upload",
            files={"file": ("sample_floorplan_studio.png", f, "image/png")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["summary"]["room_count"] == 1
    assert body["summary"]["door_count"] == 1
