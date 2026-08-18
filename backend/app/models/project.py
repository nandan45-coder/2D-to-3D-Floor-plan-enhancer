"""
Project ORM model.

This is the root record every other module (floorplan, detection,
corrections, 3D, estimation, sustainability, export) will eventually attach
to via project_id. Kept intentionally minimal in Prompt 2.

Prompt 4 adds `floorplan_data`: the single JSONB column capable of storing a
project's FloorPlan document (see app/floorplan/schema.py for the contract
that data must conform to). This is deliberately a single "current" document
for now, not a version history -- Phase 2/3 (detection + correction) will
decide how raw-detection vs. corrected versions are represented on top of
this column without changing its type or name.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# JSON on SQLite/generic backends (used in local dev/tests), JSONB on
# PostgreSQL (the target production database) -- same column, no code
# branching needed elsewhere.
_JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created")

    # Holds a single FloorPlan JSON document (see app/floorplan/schema.py).
    # Nullable: a freshly created project has no FloorPlan until Phase 2
    # (detection) or Phase 3 (manual creation) populates it.
    floorplan_data: Mapped[Optional[dict[str, Any]]] = mapped_column(_JSONVariant, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Project id={self.id!r} name={self.name!r} status={self.status!r}>"
