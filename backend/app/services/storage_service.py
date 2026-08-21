"""
Storage service: saving uploaded files to disk (local storage per config).

Per Prompt 7's constraint, this is the ONLY place that writes uploaded file
bytes to disk -- route handlers must call into this service rather than
writing files themselves, so storage location/layout can change (e.g. to
object storage) without touching route logic.

Reuses the file-type and size limits already defined in
app/cv/preprocessing.py (Prompt 6) rather than redefining them here, so
there's exactly one place those limits are configured.
"""
import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import PayloadTooLargeError, UnsupportedMediaTypeError
from app.cv.preprocessing import MAX_UPLOAD_BYTES, SUPPORTED_EXTENSIONS

# Read in chunks rather than the whole file at once, so a maliciously large
# upload can't exhaust memory before the size check ever gets a chance to run.
_READ_CHUNK_BYTES = 1024 * 1024  # 1 MB


def _validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedMediaTypeError(
            f"Unsupported file type '{ext or '(none)'}'. Supported types: {sorted(SUPPORTED_EXTENSIONS)}",
            details={"filename": filename, "supported_extensions": sorted(SUPPORTED_EXTENSIONS)},
        )
    return ext


def _project_upload_dir(project_id: str) -> Path:
    upload_dir = Path(settings.storage_path) / project_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def _write_validated(destination: Path, stream: BinaryIO) -> int:
    """Streams `stream` to `destination` in chunks, enforcing MAX_UPLOAD_BYTES as it goes."""
    total_bytes = 0
    with open(destination, "wb") as out_file:
        while True:
            chunk = stream.read(_READ_CHUNK_BYTES)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > MAX_UPLOAD_BYTES:
                out_file.close()
                destination.unlink(missing_ok=True)
                raise PayloadTooLargeError(
                    f"File exceeds the maximum allowed size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                    details={"max_bytes": MAX_UPLOAD_BYTES},
                )
            out_file.write(chunk)
    return total_bytes


def save_upload(project_id: str, upload_file: UploadFile) -> Path:
    """
    Validates and saves an uploaded floor plan file for a project.

    Returns the path it was saved to. Raises UnsupportedMediaTypeError if
    the extension isn't supported, or PayloadTooLargeError if it exceeds
    MAX_UPLOAD_BYTES (checked as the file streams to disk, not trusted from
    a client-provided header).
    """
    if not upload_file.filename:
        raise UnsupportedMediaTypeError("Uploaded file has no filename.")

    ext = _validate_extension(upload_file.filename)

    upload_dir = _project_upload_dir(project_id)
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    destination = upload_dir / stored_filename

    _write_validated(destination, upload_file.file)

    return destination
