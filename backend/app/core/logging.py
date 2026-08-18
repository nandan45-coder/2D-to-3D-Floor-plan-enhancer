"""
Structured logging configuration.

Call `setup_logging()` once at application startup (done in app/main.py).
Every module should then use `logging.getLogger(__name__)` as normal --
this module only configures the root handler/formatter.
"""
import logging
import sys

from app.core.config import settings


class _RequestSafeFormatter(logging.Formatter):
    """
    Formatter producing a single-line, structured-ish log record:
    timestamp | level | logger name | message
    Kept dependency-free (no python-json-logger) to keep the foundation minimal.
    """

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )


def setup_logging() -> None:
    """Configure the root logger once. Safe to call multiple times."""
    root_logger = logging.getLogger()

    if root_logger.handlers:
        # Already configured (e.g. re-entrant call during tests/reload).
        root_logger.setLevel(settings.log_level.upper())
        return

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(_RequestSafeFormatter())

    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers unless we're debugging.
    if level > logging.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging configured (level=%s, env=%s)", settings.log_level.upper(), settings.app_env
    )
