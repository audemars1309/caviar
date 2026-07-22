from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.v1.router import api_router
from app.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIDMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.startup import enforce_startup_configuration
from app.version import __version__

logger = logging.getLogger("caviar.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: validate configuration on boot, log lifecycle."""
    settings = get_settings()
    enforce_startup_configuration(settings)
    logger.info(
        "Caviar starting: version=%s environment=%s prefix=%s",
        __version__,
        settings.APP_ENV,
        settings.API_V1_PREFIX,
    )
    yield
    logger.info("Caviar shutting down.")


def _trusted_hosts(settings: Settings) -> list[str]:
    """Allowed Host header values. Empty config = allow all (dev default)."""
    if not settings.ALLOWED_HOSTS:
        return ["*"]
    return [host.strip() for host in settings.ALLOWED_HOSTS.split(",") if host.strip()]


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    is_production = settings.APP_ENV == "production"

    app = FastAPI(
        title=settings.APP_NAME,
        version=__version__,
        description="Caviar - AI-powered career intelligence and candidate performance platform.",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if not is_production else None,
        docs_url=f"{settings.API_V1_PREFIX}/docs" if not is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Middleware order: the last added runs outermost. Security headers
    # should wrap everything so they are present even on error responses;
    # the request-ID middleware must run early so its ID is available to
    # all inner layers and logging.
    app.add_middleware(SecurityHeadersMiddleware, production=is_production)
    app.add_middleware(RequestIDMiddleware)

    trusted_hosts = _trusted_hosts(settings)
    if trusted_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)

    cors_origins = settings.cors_origins_list
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
        )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
