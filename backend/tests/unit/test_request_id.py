from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.middleware import _sanitize_incoming_request_id


class TestSanitizeIncomingRequestId:
    def test_valid_id_is_accepted(self) -> None:
        assert _sanitize_incoming_request_id("abc-123_XYZ") == "abc-123_XYZ"

    def test_none_is_rejected(self) -> None:
        assert _sanitize_incoming_request_id(None) is None

    def test_empty_is_rejected(self) -> None:
        assert _sanitize_incoming_request_id("") is None

    def test_overlong_id_is_rejected(self) -> None:
        assert _sanitize_incoming_request_id("a" * 129) is None

    def test_max_length_id_is_accepted(self) -> None:
        assert _sanitize_incoming_request_id("a" * 128) == "a" * 128

    def test_log_injection_characters_are_rejected(self) -> None:
        assert _sanitize_incoming_request_id("abc\ndef") is None
        assert _sanitize_incoming_request_id("abc def") is None
        assert _sanitize_incoming_request_id("abc|def") is None
        assert _sanitize_incoming_request_id("<script>") is None
        assert _sanitize_incoming_request_id("abc\x00def") is None


@pytest.mark.asyncio
async def test_invalid_incoming_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/health", headers={"X-Request-ID": "bad value\nwith newline"}
    )
    assert response.status_code == 200
    returned = response.headers["x-request-id"]
    # Replaced with a server-generated hex UUID, not the malicious value.
    assert returned != "bad value\nwith newline"
    assert len(returned) == 32
    assert all(c in "0123456789abcdef" for c in returned)


@pytest.mark.asyncio
async def test_overlong_incoming_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "x" * 500})
    assert response.status_code == 200
    assert response.headers["x-request-id"] != "x" * 500
    assert len(response.headers["x-request-id"]) == 32


@pytest.mark.asyncio
async def test_valid_incoming_request_id_still_echoed(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["x-request-id"] == "trace-abc-123"
