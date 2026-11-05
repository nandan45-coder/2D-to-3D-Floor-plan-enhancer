"""
Project ORM model -- the root record every module attaches to via project_id.

- `floorplan_data` (Prompt 4): the project's current FloorPlan document (app/floorplan/schema.py). The raw detection
  result is kept separately in `<storage>/<id>/detection_snapshot.json` (Prompt 11) for "Reset to detected".
- `detection_status` / `detection_error` (Prompt 7): outcome of the latest detection run ("not_started" | "processing"
  | "complete" | "failed" | "skipped" for a drawn plan). A run interrupted by a server stop is marked "failed" at the
  next start (Prompt 34).
- `status`: kept for API compatibility; always "created". `stage` (UI-1) is the project's status (deprecated field,
  docs/INTEGRATION_PLAN.md I-13).
- `owner_id` (UI-2), activities / progress / unlocks (UI-3; Prompt 34: a new plan resets the 3D step).
Schema changes are Alembic migrations (backend/migrations), applied automatically at startup.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# JSON on SQLite/generic backends (used in local dev/tests), JSONB on
# PostgreSQL (the target production database) -- same column, no code
# branching needed elsewhere.
_JSONVariant = JSON().with_variant(JSONB(), "postgresql")

DETECTION_STATUS_VALUES = ("not_started", "processing", "complete", "failed", "skipped")
PLAN_START_KINDS = ("plan_uploaded", "plan_drawn")   # activity kinds that start a new plan (see unlocks)


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
    # UI-2: the account the project belongs to (None only for projects made before accounts, until the first
    # account adopts them). Indexed for the per-user project list.
    owner_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    @property
    def stage(self) -> str:
        """
        The project's status for the UI (UI-1): "processing" (detection running), "draft" (no plan, or a blank drawn
        sheet), "needs_review" (a detected plan the user has not saved yet, or a saved plan without rooms or walls),
        "ready" (saved with rooms and walls -- saved plans have passed validation).
        """
        if self.detection_status == "processing":
            return "processing"
        doc = self.floorplan_data or {}
        rooms, walls = len(doc.get("rooms") or []), len(doc.get("walls") or [])
        if not doc or (rooms == 0 and walls == 0):
            return "draft"
        revision = (((doc.get("metadata") or {}).get("extra") or {}).get("editor") or {}).get("revision", 0) or 0
        if revision == 0 and self.plan_origin == "uploaded":
            return "needs_review"
        return "ready" if rooms and walls else "needs_review"

    # UI-3: progress milestones and module locks (activities: app/models/activity.py)
    activities = relationship("ProjectActivity", primaryjoin="Project.id == foreign(ProjectActivity.project_id)",
                              viewonly=True, lazy="selectin")

    def viewed_current_plan_in_3d(self) -> bool:
        """Was the 3D view opened AFTER the current plan was started (upload or blank sheet)? Prompt 34 (I-4): a new
        plan locks the analysis workspaces again until it has been checked in 3D. Activity ids give the order."""
        acts = self.activities or []
        started = max((a.id for a in acts if a.kind in PLAN_START_KINDS), default=0)
        return any(a.kind == "viewed_3d" and a.id > started for a in acts)

    def _has_rooms_and_walls(self) -> bool:
        doc = self.floorplan_data or {}
        return bool(doc.get("rooms")) and bool(doc.get("walls"))

    @property
    def progress(self) -> dict:
        """x / 6: plan created, plan saved, 3D viewed, estimate reviewed, sustainability reviewed, report downloaded."""
        kinds = {a.kind for a in (self.activities or [])}
        steps = [
            ("plan_created", "Plan created", bool(self.floorplan_data)),
            ("plan_saved", "Plan saved", self.stage == "ready"),
            ("viewed_3d", "3D viewed", self.viewed_current_plan_in_3d()),
            ("estimation_viewed", "Estimate reviewed", "estimation_viewed" in kinds),
            ("sustainability_viewed", "Sustainability reviewed", "sustainability_viewed" in kinds),
            ("report_downloaded", "Report downloaded", "report_downloaded" in kinds),
        ]
        return {"done": sum(1 for *_, d in steps if d), "total": len(steps),
                "steps": [{"key": k, "label": label, "done": d} for k, label, d in steps]}

    @property
    def unlocks(self) -> dict:
        """3D: a plan with rooms and walls that is saved (or was already opened in 3D -- projects from before UI-3).
        Analysis (assistant, estimation, sustainability, report): once the 3D view of such a plan has been opened."""
        viewed = self.viewed_current_plan_in_3d()
        plan_ok = self._has_rooms_and_walls()
        return {"viewer": plan_ok and (self.stage == "ready" or viewed), "analysis": plan_ok and viewed}

    @property
    def room_count(self) -> int:
        return len((self.floorplan_data or {}).get("rooms") or [])

    @property
    def plan_origin(self) -> Optional[str]:
        """"drawn" (Draw your own floor plan, Prompt 32A), "uploaded" (detected from an upload) or None (no plan)."""
        if not self.floorplan_data:
            return None
        extra = (self.floorplan_data.get("metadata") or {}).get("extra") or {}
        return "drawn" if extra.get("origin") == "drawn" else "uploaded"

    # Status of the most recent detection run. See module docstring.
    detection_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    detection_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Project id={self.id!r} name={self.name!r} status={self.status!r}>"
