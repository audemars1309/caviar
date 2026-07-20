"""Tests for security response headers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security_headers import SecurityHeadersMiddleware


def _client(*, production: bool) -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, production=production)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    return TestClient(app)


def test_core_security_headers_present() -> None:
    response = _client(production=False).get("/ping")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "Content-Security-Policy" in response.headers


def test_hsts_only_in_production() -> None:
    assert "Strict-Transport-Security" not in _client(production=False).get("/ping").headers
    assert "Strict-Transport-Security" in _client(production=True).get("/ping").headers
