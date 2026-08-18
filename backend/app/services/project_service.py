"""
Project service -- base CRUD only.

Per Prompt 2 scope: create, list, get. No floor-plan logic here; that is
layered on in later phases (floorplan_service.py, Prompt 7+) without
modifying this file's public interface.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_project(self, payload: ProjectCreate) -> Project:
        project = Project(name=payload.name, description=payload.description)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list_projects(self, limit: int = 100, offset: int = 0) -> List[Project]:
        stmt = select(Project).order_by(Project.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.execute(stmt).scalars().all())

    def get_project(self, project_id: str) -> Project:
        project = self.db.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"Project '{project_id}' was not found.")
        return project

    def get_project_or_none(self, project_id: str) -> Optional[Project]:
        return self.db.get(Project, project_id)

    def update_project(self, project_id: str, payload: ProjectUpdate) -> Project:
        project = self.get_project(project_id)
        if payload.name is not None:
            project.name = payload.name
        if payload.description is not None:
            project.description = payload.description
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete_project(self, project_id: str) -> None:
        project = self.get_project(project_id)
        self.db.delete(project)
        self.db.commit()
