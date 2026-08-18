"""
Project CRUD routes -- basic create/list/get(/update/delete).

No floor-plan, detection, or estimation logic is exposed here. Those get
their own route modules in later phases and are aggregated in
app/api/router.py alongside this one.
"""
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectRead:
    service = ProjectService(db)
    project = service.create_project(payload)
    return project


@router.get("", response_model=List[ProjectRead])
def list_projects(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[ProjectRead]:
    service = ProjectService(db)
    return service.list_projects(limit=limit, offset=offset)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectRead:
    service = ProjectService(db)
    return service.get_project(project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)) -> ProjectRead:
    service = ProjectService(db)
    return service.update_project(project_id, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)) -> None:
    service = ProjectService(db)
    service.delete_project(project_id)
