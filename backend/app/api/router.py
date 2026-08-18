"""
Central API router.

Every feature router (projects, floorplans, detection, corrections,
models_3d, assistant, estimation, sustainability) gets included here as it
is built, so app/main.py only ever needs to mount this one router. This is
what keeps routers "easy to add to without editing unrelated files."
"""
from fastapi import APIRouter

from app.api.routes import projects
from app.core.config import settings
from app.core.database import check_database_connection

api_router = APIRouter()

api_router.include_router(projects.router)


@api_router.get("/health", tags=["health"])
def health_check() -> dict:
    """
    Service + database health check.

    Returns 200 with status details whether or not the DB is reachable --
    the payload's `database` field carries connectivity status so callers
    (and monitoring) can distinguish "API up, DB down" from "fully healthy".
    """
    db_ok = check_database_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "service": settings.app_name,
        "environment": settings.app_env,
        "database": "connected" if db_ok else "unreachable",
    }
