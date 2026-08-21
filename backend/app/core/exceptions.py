"""
Application-level exceptions.

Services raise these instead of HTTPException directly, so service logic
stays framework-agnostic and reusable outside of request handling (e.g. from
scripts or background tasks). The API layer's exception handlers (see
app/main.py) translate these into the consistent JSON error format.
"""


class AppError(Exception):
    """Base class for all application-raised errors."""
    code: str = "APP_ERROR"
    status_code: int = 500

    def __init__(self, message: str, details=None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    status_code = 422


class UnsupportedMediaTypeError(AppError):
    """Raised when an uploaded file's type isn't supported (e.g. wrong extension)."""
    code = "UNSUPPORTED_MEDIA_TYPE"
    status_code = 415


class PayloadTooLargeError(AppError):
    """Raised when an uploaded file exceeds the configured size limit."""
    code = "PAYLOAD_TOO_LARGE"
    status_code = 413


class ConflictError(AppError):
    """Raised when a request is valid but the resource isn't in the right state yet (e.g. detection result requested before detection has completed)."""
    code = "CONFLICT"
    status_code = 409
