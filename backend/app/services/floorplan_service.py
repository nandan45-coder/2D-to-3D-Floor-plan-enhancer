"""
FloorPlan persistence service.

Owns reading/writing Project.floorplan_data. Every write goes through the
Prompt 4 schema validator (app.floorplan.validator.parse_floorplan) first --
this service is not a thin passthrough to the database; it's the boundary
that guarantees nothing invalid ever gets persisted, regardless of which
caller (detection, correction editor, etc.) is writing.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.floorplan.validator import parse_floorplan
from app.models.project import Project
from app.services.project_service import ProjectService


class FloorPlanService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.project_service = ProjectService(db)

    def save_floorplan(self, project_id: str, floorplan_dict: dict) -> dict:
        """
        Validates `floorplan_dict` against the canonical schema and persists
        it as the project's current FloorPlan document. Raises
        ValidationAppError (via parse_floorplan) if it doesn't validate --
        an invalid FloorPlan is never written to the database.
        """
        project = self.project_service.get_project(project_id)  # raises NotFoundError if missing
        validated = parse_floorplan(floorplan_dict)

        project.floorplan_data = validated.model_dump(mode="json")
        self.db.commit()
        self.db.refresh(project)
        return project.floorplan_data

    def get_floorplan(self, project_id: str) -> Optional[dict]:
        project = self.project_service.get_project(project_id)
        return project.floorplan_data

    def require_floorplan(self, project_id: str) -> dict:
        """Like get_floorplan, but raises ConflictError (409) instead of returning None."""
        floorplan = self.get_floorplan(project_id)
        if floorplan is None:
            raise ConflictError(
                f"Project '{project_id}' has no FloorPlan yet. Run detection or create one first."
            )
        return floorplan

    # --- Detection status tracking (Prompt 7) --------------------------------

    def set_detection_status(self, project_id: str, status: str, error: Optional[str] = None) -> Project:
        project = self.project_service.get_project(project_id)
        project.detection_status = status
        project.detection_error = error
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_detection_status(self, project_id: str) -> dict:
        project = self.project_service.get_project(project_id)
        return {"status": project.detection_status, "error": project.detection_error}
