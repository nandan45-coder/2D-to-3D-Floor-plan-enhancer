"""
Pydantic schemas for the detection API (Prompt 7).

The full FloorPlan result itself is returned as the raw validated dict
produced by app.floorplan.schema.FloorPlan.model_dump() -- these schemas
cover the lighter-weight status/summary responses used around it.
"""
from typing import Optional

from pydantic import BaseModel


class DetectionStatusResponse(BaseModel):
    status: str  # "not_started" | "processing" | "complete" | "failed"
    error: Optional[str] = None


class DetectionSummary(BaseModel):
    """Element counts + calibration info, for a quick at-a-glance result without the full FloorPlan payload."""
    room_count: int
    wall_count: int
    door_count: int
    window_count: int
    stair_count: int
    dimension_count: int
    calibration_source: Optional[str] = None
    notes: Optional[str] = None


class DetectionUploadResponse(DetectionStatusResponse):
    summary: Optional[DetectionSummary] = None
