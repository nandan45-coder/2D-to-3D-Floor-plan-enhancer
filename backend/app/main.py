"""
FastAPI application entry point.

Run locally with:
    uvicorn app.main:app --reload --app-dir backend

Responsibilities kept here, and only here:
    - app instantiation
    - middleware (CORS)
    - global exception handlers (consistent JSON error format)
    - startup/shutdown hooks
    - mounting the central api_router

Feature logic lives in app/api/routes/*, app/services/*, and the
domain modules (cv, ocr, floorplan, three_d, llm, estimation,
sustainability) added in later phases.
"""
import logging
from contextlib import asynccontextmanager

from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import AppError
from app.core.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def _recover_interrupted_detections() -> None:
    """Prompt 34: detection runs inside the upload request, so a run marked "processing" at startup was interrupted."""
    from app.core.database import SessionLocal
    from app.services.floorplan_service import FloorPlanService

    db = SessionLocal()
    try:
        fixed = FloorPlanService(db).recover_interrupted_detections()
        if fixed:
            logger.warning("Marked %d interrupted detection run(s) as failed", fixed)
    except Exception:  # noqa: BLE001 -- never block startup over this
        logger.exception("Could not check for interrupted detection runs")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (env=%s)", settings.app_name, settings.app_env)
    for warning in settings.production_warnings():
        logger.warning("Production setting: %s", warning)
    init_db()
    _recover_interrupted_detections()
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="0.1.0",
    lifespan=lifespan,
    # Prompt 39: the API explorer is a development tool -- hidden in production (ENABLE_API_DOCS=true shows it)
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)


# --- Security headers (Prompt 39) -------------------------------------------
# The API answers JSON, images, PDFs and SVG thumbnails: none of it may be sniffed as another type, framed by another
# site, or sent with a full referrer. (The website's own headers are set by nginx, docker/nginx.conf.)
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response

# --- CORS -------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Global exception handlers -----------------------------------------
# Every error response follows the same shape:
#   {"error": {"code": str, "message": str, "details": Any | null}}

def _error_body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning("AppError on %s %s: %s", request.method, request.url.path, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message, exc.details),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: str})   # Prompt 38: ctx can hold exceptions
    # a validator's own sentence ("Give the project a name.") is shown as the message; otherwise the generic one
    own = next((e.get("msg", "")[len("Value error, "):] for e in errors if e.get("type") == "value_error"), "")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body("VALIDATION_ERROR", own or "Request validation failed.", errors),
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body("HTTP_ERROR", str(exc.detail)),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    # Never leak internals (stack traces, exception repr) to the client.
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("INTERNAL_SERVER_ERROR", "Something went wrong on the server. Try again; if it keeps happening, "
                                                     "the backend terminal shows the details."),
    )
    # Prompt 38 (P37-04): this response is produced outside the CORS middleware, so without these headers the browser
    # hides it and the website wrongly reports that the backend is not running.
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


# --- Routes ---------------------------------------------------------------
app.include_router(api_router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {"service": settings.app_name, "status": "running", "docs": "/docs"}
