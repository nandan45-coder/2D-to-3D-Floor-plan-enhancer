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
