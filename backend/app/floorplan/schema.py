"""
The canonical FloorPlan data contract.

Every major subsystem (detection, correction editor, 3D generation, LLM
assistant, estimation, sustainability, export) reads from or writes to this
single representation. See docs/ARCHITECTURE.md Section 4 and
docs/FLOORPLAN_SCHEMA.md for the authoritative field-by-field description.

STABILITY RULE (per ARCHITECTURE.md): no subsystem may introduce a new
top-level field or change the meaning of an existing field here without
updating docs/FLOORPLAN_SCHEMA.md and docs/ARCHITECTURE.md. This file is
purely structural/geometric plus metadata -- feature-specific results
(estimation, sustainability scores, etc.) must NOT be added here; they are
computed on demand from this data by their own modules.

Coordinate system: 2D, origin at the top-left of the source floor plan
image/drawing, x increasing rightward, y increasing downward (standard
image/screen convention). See docs/FLOORPLAN_SCHEMA.md for how this maps to
the 3D scene's coordinate system in Phase 4.
"""
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Source of an element: populated by AI detection, or created/edited by hand
# in the 2D correction editor. Kept to exactly these two values per the
# contract already committed to in docs/ARCHITECTURE.md Section 4.
SourceType = Literal["ai_detection", "manual_correction"]

Units = Literal["feet", "meters", "inches", "centimeters"]

WallType = Literal["exterior", "interior"]

DoorSwing = Literal["left", "right", "sliding", "none"]


class Point2D(BaseModel):
    """A single coordinate in the FloorPlan's 2D coordinate system."""
    x: float
    y: float


class ElementBase(BaseModel):
    """Fields shared by every element type (room, wall, door, window, stair, etc.)."""
    id: str = Field(..., min_length=1, description="Unique within this FloorPlan document.")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="AI detection confidence (0-1). Omitted or 1.0 for manually created/corrected elements.",
    )
    source: SourceType = Field(
        default="manual_correction",
        description="Whether this element came from AI detection or manual editing.",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Element-specific free-form metadata.")


class Room(ElementBase):
    name: str = Field(..., min_length=1)
    polygon: List[Point2D] = Field(..., min_length=3, description="Ordered vertices forming a closed room boundary.")
    room_type: Optional[str] = Field(default=None, description="e.g. 'bedroom', 'kitchen', 'bathroom'.")


class Wall(ElementBase):
    start: Point2D
    end: Point2D
    thickness: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)
    wall_type: WallType = "interior"


class Door(ElementBase):
    wall_id: str = Field(..., description="id of the Wall this door is set into.")
    position: float = Field(..., ge=0.0, le=1.0, description="Normalized position along the wall, start=0, end=1.")
    width: float = Field(..., gt=0)
    height: Optional[float] = Field(default=None, gt=0)
    swing: Optional[DoorSwing] = None


class Window(ElementBase):
    wall_id: str = Field(..., description="id of the Wall this window is set into.")
    position: float = Field(..., ge=0.0, le=1.0, description="Normalized position along the wall, start=0, end=1.")
    width: float = Field(..., gt=0)
    height: Optional[float] = Field(default=None, gt=0)
    sill_height: Optional[float] = Field(default=None, ge=0)


class Stair(ElementBase):
    polygon: List[Point2D] = Field(..., min_length=3, description="Footprint of the staircase.")
    step_count: Optional[int] = Field(default=None, gt=0)
    direction: Optional[str] = Field(default=None, description="e.g. 'up', 'down'.")


class DimensionAnnotation(ElementBase):
    """An OCR-extracted or manually placed measurement line/label."""
    start: Point2D
    end: Point2D
    value: float = Field(..., gt=0)
    label: Optional[str] = Field(default=None, description="Raw text as extracted/entered, e.g. '12ft 6in'.")


class FurnitureItem(ElementBase):
    furniture_type: str = Field(..., min_length=1, description="e.g. 'bed', 'sofa', 'dining_table'.")
    position: Point2D
    rotation: float = Field(default=0.0, description="Degrees, clockwise from the coordinate system's +x axis.")
    width: Optional[float] = Field(default=None, gt=0)
    depth: Optional[float] = Field(default=None, gt=0)
    height: Optional[float] = Field(default=None, gt=0)
    room_id: Optional[str] = Field(default=None, description="id of the Room this item is placed in, if known.")


class FloorPlanMetadata(BaseModel):
    """Document-level metadata. Distinct from per-element `metadata` on ElementBase."""
    building_name: Optional[str] = None
    detection_version: Optional[str] = Field(default=None, description="Version tag of the detection pipeline used.")
    source_image_reference: Optional[str] = Field(default=None, description="Path/reference to the uploaded source file.")
    notes: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class FloorPlan(BaseModel):
    """
    The top-level FloorPlan document -- the shared contract itself.

    This shape must stay backward compatible. Adding a new *optional* field
    to an existing element type is acceptable; removing or repurposing an
    existing field, or adding new top-level collections, requires updating
    docs/FLOORPLAN_SCHEMA.md and docs/ARCHITECTURE.md first.
    """
    project_id: str = Field(..., min_length=1)
    units: Units = "feet"

    rooms: List[Room] = Field(default_factory=list)
    walls: List[Wall] = Field(default_factory=list)
    doors: List[Door] = Field(default_factory=list)
    windows: List[Window] = Field(default_factory=list)
    stairs: List[Stair] = Field(default_factory=list)
    dimensions: List[DimensionAnnotation] = Field(default_factory=list)
    furniture: List[FurnitureItem] = Field(default_factory=list)

    metadata: FloorPlanMetadata = Field(default_factory=FloorPlanMetadata)

    @field_validator("project_id")
    @classmethod
    def _project_id_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("project_id must not be blank")
        return value
