"""
Shared base Pydantic schemas used across every feature module.

Feature-specific schemas (floorplan, detection, estimation, etc.) are added
in their respective phases and should build on these bases rather than
redefining error/response conventions.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ORMBase(BaseModel):
    """Base for schemas that read directly from SQLAlchemy ORM objects."""
    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None


class ErrorResponse(BaseModel):
    """
    Consistent JSON error shape returned by every global exception handler.

    Example:
        {
            "error": {
                "code": "NOT_FOUND",
                "message": "Project 'abc123' was not found.",
                "details": null
            }
        }
    """
    error: ErrorDetail


class TimestampedSchema(ORMBase):
    created_at: datetime
    updated_at: datetime
