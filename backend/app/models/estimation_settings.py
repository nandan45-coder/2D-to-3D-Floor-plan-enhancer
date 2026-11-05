"""
Per-project estimation settings (Prompt 28, docs/ESTIMATION_DESIGN.md Section 9).

Stores only the values the user CHANGED (sparse overrides, e.g. {"rates": {"cement": 450}}), so improved
defaults reach every project that did not override them. A separate table keeps the FloorPlan contract
untouched; it is created automatically at startup (Base.metadata.create_all), no migration needed.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class EstimationSettings(Base):
    __tablename__ = "estimation_settings"

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
