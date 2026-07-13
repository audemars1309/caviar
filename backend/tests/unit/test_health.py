from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"] == "Caviar"
    assert body["environment"] == "test" or body["environment"] == "development"


async def test_health_check_has_request_id_header(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


async def test_incoming_request_id_is_echoed_back(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "test-correlation-id"})
    assert response.headers["x-request-id"] == "test-correlation-id"


async def test_unknown_route_returns_structured_404(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "http_error"


async def test_wrong_method_returns_structured_error(client: AsyncClient) -> None:
    # No route in Phase 1 accepts a request body, so there is nothing yet to
    # exercise FastAPI's RequestValidationError handler with. Calling an
    # existing route with an unsupported HTTP method exercises the same
    # centralized-error-response code path (a non-2xx StarletteHTTPException)
    # that a future validation error would also flow through, without
    # inventing a fake request body.
    response = await client.post("/api/v1/health")
    assert response.status_code == 405
    body = response.json()
    assert body["error"]["code"] == "http_error"
