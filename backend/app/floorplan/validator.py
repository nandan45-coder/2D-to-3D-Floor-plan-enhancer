"""
Structural validation for FloorPlan documents.

Pydantic (schema.py) enforces field-level correctness (types, ranges,
required fields). This module enforces *structural* correctness that spans
multiple elements -- things Pydantic's per-field validators can't see:

    - every element id is unique across the whole document
    - every door/window references a wall_id that actually exists
    - every furniture room_id (if set) references a room that actually exists

Used by:
    - backend/tests/test_floorplan_schema.py (direct validation tests)
    - the 2D correction editor's save path (Phase 3, Prompt 11) to reject
      structurally broken FloorPlans before persisting
"""
from typing import List, Tuple

from pydantic import ValidationError

from app.core.exceptions import ValidationAppError
from app.floorplan.schema import FloorPlan


class FloorPlanValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], floorplan: FloorPlan | None = None) -> None:
        self.is_valid = is_valid
        self.errors = errors
        self.floorplan = floorplan


def _check_structural_rules(floorplan: FloorPlan) -> List[str]:
    errors: List[str] = []

    # --- Uniqueness of ids across every element collection -----------------
    all_ids: List[Tuple[str, str]] = []  # (collection_name, id)
    for collection_name in ("rooms", "walls", "doors", "windows", "stairs", "dimensions", "furniture"):
        for element in getattr(floorplan, collection_name):
            all_ids.append((collection_name, element.id))

    seen: set[str] = set()
    for collection_name, element_id in all_ids:
        if element_id in seen:
            errors.append(f"Duplicate element id '{element_id}' found in '{collection_name}'.")
        seen.add(element_id)

    # --- Referential integrity: doors/windows -> walls ----------------------
    wall_ids = {wall.id for wall in floorplan.walls}
    for door in floorplan.doors:
        if door.wall_id not in wall_ids:
            errors.append(f"Door '{door.id}' references unknown wall_id '{door.wall_id}'.")
    for window in floorplan.windows:
        if window.wall_id not in wall_ids:
            errors.append(f"Window '{window.id}' references unknown wall_id '{window.wall_id}'.")

    # --- Referential integrity: furniture -> rooms (optional reference) -----
    room_ids = {room.id for room in floorplan.rooms}
    for item in floorplan.furniture:
        if item.room_id is not None and item.room_id not in room_ids:
            errors.append(f"Furniture '{item.id}' references unknown room_id '{item.room_id}'.")

    return errors


def validate_floorplan(data: dict) -> FloorPlanValidationResult:
    """
    Validate a raw dict against the FloorPlan schema, then run structural
    (cross-element) checks. Never raises -- callers inspect `.is_valid` /
    `.errors`. Use `parse_floorplan` instead if you want an exception on
    failure.
    """
    errors: List[str] = []

    try:
        floorplan = FloorPlan.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"])
            errors.append(f"{loc}: {err['msg']}")
        return FloorPlanValidationResult(is_valid=False, errors=errors, floorplan=None)

    structural_errors = _check_structural_rules(floorplan)
    if structural_errors:
        return FloorPlanValidationResult(is_valid=False, errors=structural_errors, floorplan=None)

    return FloorPlanValidationResult(is_valid=True, errors=[], floorplan=floorplan)


def parse_floorplan(data: dict) -> FloorPlan:
    """
    Validate and return a FloorPlan, raising ValidationAppError (mapped to a
    422 with the standard {"error": {...}} shape by app/main.py) on failure.
    """
    result = validate_floorplan(data)
    if not result.is_valid:
        raise ValidationAppError("FloorPlan document failed validation.", details=result.errors)
    assert result.floorplan is not None  # guaranteed by is_valid=True
    return result.floorplan
