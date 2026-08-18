"""
SQLAlchemy models package.

Prompt 2 introduces only the base Project record. FloorPlan JSON storage
(JSONB column / relationship) is added in Prompt 4 once the schema is
finalized -- see ARCHITECTURE.md's FloorPlan Data Contract section.
"""
from app.models.project import Project  # noqa: F401
