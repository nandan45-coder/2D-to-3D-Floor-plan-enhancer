"""
Detection API routes.

Per Prompt 7's constraint ("REST polling OR simple synchronous response for
MVP status handling -- avoid building a full job queue"), upload and
detection-triggering are combined into a single synchronous endpoint: the
detection pipeline (Prompt 6) is fast enough on MVP-sized images that
running it inline within the upload request and returning the final status
is simpler and more honest than faking an async job for a same-process,
single-worker pipeline. Separate status/result GET endpoints still exist
(satisfying the 4 conceptual actions the prompt describes: upload, trigger,
check status, fetch result) so the frontend can re-query without
re-uploading, and so this contract doesn't need to change if a real
background job queue is introduced later.
"""
import logging

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.cv.detector import run_detection_pipeline
from app.schemas.detection import DetectionStatusResponse, DetectionSummary, DetectionUploadResponse
from app.services.floorplan_service import FloorPlanService
from app.services.storage_service import save_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/floorplan", tags=["detection"])


def _build_summary(floorplan_dict: dict) -> DetectionSummary:
    metadata = floorplan_dict.get("metadata") or {}
    extra = metadata.get("extra") or {}
    return DetectionSummary(
        room_count=len(floorplan_dict.get("rooms", [])),
        wall_count=len(floorplan_dict.get("walls", [])),
        door_count=len(floorplan_dict.get("doors", [])),
        window_count=len(floorplan_dict.get("windows", [])),
        stair_count=len(floorplan_dict.get("stairs", [])),
        dimension_count=len(floorplan_dict.get("dimensions", [])),
        calibration_source=extra.get("calibration_source"),
        notes=metadata.get("notes"),
    )


@router.post("/upload", response_model=DetectionUploadResponse)
def upload_and_detect(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DetectionUploadResponse:
    """
    Uploads a floor plan file and runs detection on it synchronously.

    A malformed request (unsupported file type, oversized file) fails with a
    real HTTP error (415/413) via storage_service -- that's a client error
    on the request itself. Once the file is validly stored, detection
    running but producing a low-quality/invalid result is a different kind
    of outcome: the HTTP call succeeded (a file was accepted and processed),
    so this returns 200 with status="failed" and an error message in the
    body, rather than a 500 -- letting the frontend distinguish "your
    request was bad" from "we tried, and detection didn't produce a valid
    result" (which is exactly the pattern of failure Phase 3's manual
    correction editor exists to recover from).
    """
    floorplan_service = FloorPlanService(db)
    # Raises NotFoundError (404) if the project doesn't exist -- fail fast,
    # before touching the filesystem or running any detection work.
    floorplan_service.project_service.get_project(project_id)

    saved_path = save_upload(project_id, file)  # raises 415/413 on invalid input

    floorplan_service.set_detection_status(project_id, "processing")

    try:
        floorplan_dict = run_detection_pipeline(str(saved_path), project_id)
        saved = floorplan_service.save_floorplan(project_id, floorplan_dict)
        floorplan_service.set_detection_status(project_id, "complete")
        return DetectionUploadResponse(status="complete", error=None, summary=_build_summary(saved))
    except Exception as exc:  # noqa: BLE001 -- any detection failure is a "failed" outcome, not a crash
        logger.exception("Detection failed for project %s", project_id)
        error_message = str(exc)
        floorplan_service.set_detection_status(project_id, "failed", error=error_message)
        return DetectionUploadResponse(status="failed", error=error_message, summary=None)


@router.get("/status", response_model=DetectionStatusResponse)
def get_detection_status(project_id: str, db: Session = Depends(get_db)) -> DetectionStatusResponse:
    floorplan_service = FloorPlanService(db)
    status_info = floorplan_service.get_detection_status(project_id)  # raises 404 if project missing
    return DetectionStatusResponse(**status_info)


@router.get("/result")
def get_detection_result(project_id: str, db: Session = Depends(get_db)) -> dict:
    """
    Returns the persisted FloorPlan document. Raises ConflictError (409) if
    no FloorPlan exists yet for this project (distinct from 404: the
    project itself exists, it just hasn't been through detection yet).
    """
    floorplan_service = FloorPlanService(db)
    return floorplan_service.require_floorplan(project_id)
