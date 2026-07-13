"""Request-scoped context shared between middleware and the logging layer."""

from __future__ import annotations

from contextvars import ContextVar

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="-")
