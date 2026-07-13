"""Structured logging setup.

Per the master specification's observability requirements: log request
correlation IDs, keep the format structured/parseable, and never log
sensitive data. Phase 1 does not yet log AI operations, transcription, or
TTS durations - those are added in the phases that introduce those
subsystems.
"""

from __future__ import annotations

import logging
import sys

from app.config import get_settings
from app.core.context import request_id_ctx_var


class _RequestContextFilter(logging.Filter):
    """Attaches the current request's correlation ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx_var.get()
        return True


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | request_id=%(request_id)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(_RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    if not settings.DEBUG:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
