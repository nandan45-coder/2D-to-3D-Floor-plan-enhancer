"""
Pydantic schemas for the base Project resource.

NOTE: This is project-record CRUD only (id, name, description, status,
timestamps). No FloorPlan JSON lives here yet -- that contract is owned by
app/floorplan (finalized in Prompt 4) and will be attached to a Project via
a separate relationship/column in a later phase, per the "no floor-plan
logic yet" constraint on this prompt.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.base import ORMBase


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class ProjectRead(ORMBase):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
