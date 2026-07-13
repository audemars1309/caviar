from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import request_id_ctx_var

# Phase 2 review observation #1: an incoming X-Request-ID is caller-controlled
# input that gets reflected into every log line for the request. Without a
# length/charset constraint, a caller could inject oversized or malformed
# values into logs. Only a bounded, safe-charset value is honored; anything
# else is replaced with a fresh server-generated ID rather than reflected.
_MAX_REQUEST_ID_LENGTH = 128
_SAFE_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _sanitize_incoming_request_id(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    if len(raw_value) > _MAX_REQUEST_ID_LENGTH:
        return None
    if not _SAFE_REQUEST_ID_PATTERN.match(raw_value):
        return None
    return raw_value


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns a correlation ID to every request.

    The ID is read from an incoming ``X-Request-ID`` header if the caller
    supplied one *and* it passes the length/charset check above; otherwise
    a new one is generated. It is exposed on the response and made
    available to the logging layer via a ContextVar so every log line
    emitted while handling a request can be traced back to it, without
    callers needing to pass ``extra=`` explicitly on every log call.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming_id = _sanitize_incoming_request_id(request.headers.get("X-Request-ID"))
        request_id = incoming_id if incoming_id else uuid.uuid4().hex
        token = request_id_ctx_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx_var.reset(token)
        response.headers["X-Request-ID"] = request_id
        return response
