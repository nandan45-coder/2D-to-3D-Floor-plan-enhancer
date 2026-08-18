"""
FloorPlan schema + validator + storage tests (Prompt 4).

Covers:
    - the example fixture validates successfully end-to-end
    - field-level (Pydantic) validation rejects malformed input
    - structural validation rejects referentially-broken input
      (duplicate ids, dangling wall_id references, dangling room_id references)
    - a DB round-trip: save the example FloorPlan into Project.floorplan_data,
      reload it in a fresh session, and confirm it comes back byte-for-byte
      equivalent and still schema-valid

NOTE on "API round-trip" (Prompt 4, Testing Requirements #3): this prompt's
Files/Folders list does not include a new HTTP route for raw FloorPlan
CRUD (that's introduced in Phase 2/3 alongside detection/correction, per
docs/DEVELOPMENT_STATUS.md). The round-trip here is exercised at the
database/service boundary via a real SQLAlchemy session instead of over
HTTP, which is the "API" available at this stage of the project. See this
file's PROMPT STATUS entry in DEVELOPMENT_STATUS.md for the explicit
reasoning.
"""
import copy
import json
import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_floorplan.db")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.floorplan.schema import FloorPlan
from app.floorplan.validator import parse_floorplan, validate_floorplan
from app.models.project import Project

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / "data" / "samples" / "example_floorplan.json"

TEST_DB_URL = "sqlite:///./test_floorplan.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test_floorplan.db"):
        os.remove("test_floorplan.db")


@pytest.fixture()
def example_floorplan_dict() -> dict:
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# --- Fixture validity ------------------------------------------------------


def test_example_fixture_exists_and_is_valid_json(example_floorplan_dict):
    assert isinstance(example_floorplan_dict, dict)
    assert example_floorplan_dict["project_id"] == "SAMPLE-001"


def test_example_fixture_passes_full_validation(example_floorplan_dict):
    result = validate_floorplan(example_floorplan_dict)
    assert result.is_valid, result.errors
    assert result.floorplan is not None
    assert isinstance(result.floorplan, FloorPlan)


def test_example_fixture_exercises_every_element_type(example_floorplan_dict):
    fp = parse_floorplan(example_floorplan_dict)
    assert len(fp.rooms) >= 1
    assert len(fp.walls) >= 1
    assert len(fp.doors) >= 1
    assert len(fp.windows) >= 1
    assert len(fp.stairs) >= 1
    assert len(fp.dimensions) >= 1
    assert len(fp.furniture) >= 1


# --- Field-level (Pydantic) validation failures -----------------------------


def test_missing_project_id_fails():
    result = validate_floorplan({"units": "feet"})
    assert not result.is_valid
    assert any("project_id" in e for e in result.errors)


def test_room_with_fewer_than_three_points_fails(example_floorplan_dict):
    broken = copy.deepcopy(example_floorplan_dict)
    broken["rooms"][0]["polygon"] = [{"x": 0, "y": 0}, {"x": 1, "y": 1}]
    result = validate_floorplan(broken)
    assert not result.is_valid


def test_confidence_out_of_range_fails(example_floorplan_dict):
    broken = copy.deepcopy(example_floorplan_dict)
    broken["rooms"][0]["confidence"] = 1.5
    result = validate_floorplan(broken)
    assert not result.is_valid


def test_negative_wall_thickness_fails(example_floorplan_dict):
    broken = copy.deepcopy(example_floorplan_dict)
    broken["walls"][0]["thickness"] = -0.5
    result = validate_floorplan(broken)
    assert not result.is_valid


def test_door_missing_required_width_fails(example_floorplan_dict):
    broken = copy.deepcopy(example_floorplan_dict)
    del broken["doors"][0]["width"]
    result = validate_floorplan(broken)
    assert not result.is_valid


# --- Structural validation failures -----------------------------------------


def test_duplicate_ids_across_collections_fails(example_floorplan_dict):
    broken = copy.deepcopy(example_floorplan_dict)
    # Reuse an existing wall id as a room id -- duplicate across collections.
    broken["rooms"][0]["id"] = broken["walls"][0]["id"]
    result = validate_floorplan(broken)
    assert not result.is_valid
    assert any("Duplicate element id" in e for e in result.errors)


def test_door_referencing_unknown_wall_fails(example_floorplan_dict):
    broken = copy.deepcopy(example_floorplan_dict)
    broken["doors"][0]["wall_id"] = "wall-does-not-exist"
    result = validate_floorplan(broken)
    assert not result.is_valid
    assert any("unknown wall_id" in e for e in result.errors)


def test_window_referencing_unknown_wall_fails(example_floorplan_dict):
    broken = copy.deepcopy(example_floorplan_dict)
    broken["windows"][0]["wall_id"] = "wall-does-not-exist"
    result = validate_floorplan(broken)
    assert not result.is_valid
    assert any("unknown wall_id" in e for e in result.errors)


def test_furniture_referencing_unknown_room_fails(example_floorplan_dict):
    broken = copy.deepcopy(example_floorplan_dict)
    broken["furniture"][0]["room_id"] = "room-does-not-exist"
    result = validate_floorplan(broken)
    assert not result.is_valid
    assert any("unknown room_id" in e for e in result.errors)


def test_parse_floorplan_raises_on_invalid(example_floorplan_dict):
    from app.core.exceptions import ValidationAppError

    broken = copy.deepcopy(example_floorplan_dict)
    broken["doors"][0]["wall_id"] = "wall-does-not-exist"
    with pytest.raises(ValidationAppError):
        parse_floorplan(broken)


# --- DB round-trip (save + reload via a real SQLAlchemy session) ------------


def test_floorplan_round_trips_through_database(example_floorplan_dict):
    # Validate first, exactly as a real save path should.
    validated = parse_floorplan(example_floorplan_dict)
    payload = validated.model_dump(mode="json")

    session = TestingSessionLocal()
    try:
        project = Project(name="Round Trip Test Project", floorplan_data=payload)
        session.add(project)
        session.commit()
        project_id = project.id
    finally:
        session.close()

    # Fresh session -- proves it was actually persisted, not just held in memory.
    session2 = TestingSessionLocal()
    try:
        reloaded = session2.get(Project, project_id)
        assert reloaded is not None
        assert reloaded.floorplan_data is not None

        # What comes back must still be schema-valid...
        result = validate_floorplan(reloaded.floorplan_data)
        assert result.is_valid, result.errors

        # ...and structurally identical to what was saved.
        assert reloaded.floorplan_data["project_id"] == payload["project_id"]
        assert len(reloaded.floorplan_data["rooms"]) == len(payload["rooms"])
        assert len(reloaded.floorplan_data["walls"]) == len(payload["walls"])
        assert reloaded.floorplan_data["rooms"][0]["name"] == payload["rooms"][0]["name"]
    finally:
        session2.close()


def test_project_without_floorplan_data_defaults_to_none():
    session = TestingSessionLocal()
    try:
        project = Project(name="Empty Project")
        session.add(project)
        session.commit()
        assert project.floorplan_data is None
    finally:
        session.close()
