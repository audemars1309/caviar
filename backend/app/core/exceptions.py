"""Centralized application error hierarchy and FastAPI exception handlers.

Every error raised by application/service code should be a subclass of
``AppError`` (or, for genuinely unexpected bugs, an unhandled built-in
exception, which is still caught and sanitized by the catch-all handler
below). Route handlers should not catch these individually - they are
translated to HTTP responses centrally here, so every part of the codebase
returns errors in the same shape.

This module intentionally contains no domain-specific error types yet
(e.g. resume-not-found, interview-stage-invalid). Those are added by the
services that introduce those domains, subclassing the base types defined
here.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for all application-raised errors.

    Carries an HTTP status code and a stable, machine-readable
    ``error_code`` so the frontend can branch on error type without parsing
    human-readable messages.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class ValidationFailedError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "validation_failed"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "authentication_required"


class AuthorizationError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "not_authorized"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limited"


class UpstreamServiceError(AppError):
    """Raised when a required upstream dependency (database now; storage
    and, from later phases, the AI provider / STT / TTS / LaTeX compiler)
    is unavailable or fails in a way the caller cannot recover from
    directly."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "upstream_unavailable"


def _error_response(
    status_code: int, error_code: str, message: str, details: dict[str, Any]
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {"error": {"code": error_code, "message": message, "details": details}}
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("Unhandled application error: %s", exc.message, exc_info=exc)
        return _error_response(exc.status_code, exc.error_code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "request_validation_failed",
            "The request could not be validated.",
            {"errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _error_response(exc.status_code, "http_error", str(exc.detail), {})

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception")
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
            {},
        )
