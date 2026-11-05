"""
Access control for the API (UI-2). Every route except /health and /auth/* depends on `require_access`:
  - a valid session cookie -> the signed-in user (401 otherwise);
  - if the path names a project (/projects/{project_id}/...), that project must belong to the user
    (404 otherwise -- another user's project is indistinguishable from a missing one).
"""
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.models.project import Project
from app.models.user import User
from app.services.auth_service import AuthError, AuthService


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = AuthService(db).user_for_token(request.cookies.get(settings.session_cookie_name))
    if user is None:
        raise AuthError("Sign in to continue.")
    return user


def require_access(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)) -> User:
    project_id = request.path_params.get("project_id")
    if project_id is not None:
        owner = db.query(Project.owner_id).filter(Project.id == project_id).scalar()
        if owner != user.id:
            raise NotFoundError(f"Project '{project_id}' not found.")
    request.state.user = user
    return user
