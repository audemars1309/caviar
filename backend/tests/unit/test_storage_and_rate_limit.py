"""Unit tests for the Supabase Storage REST client (against an httpx
MockTransport - no network) and the in-process rate limiter."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.core.exceptions import RateLimitedError
from app.core.rate_limit import SlidingWindowRateLimiter
from app.services.storage.supabase_storage import (
    StorageObjectNotFoundError,
    StorageOperationError,
    SupabaseStorageClient,
)

_SUPABASE_URL = "https://example-project.supabase.co"
_ANON_KEY = "anon-key-for-tests"
_TOKEN = "user-jwt-for-tests"


def _client(handler) -> SupabaseStorageClient:
    return SupabaseStorageClient(
        supabase_url=_SUPABASE_URL,
        anon_key=_ANON_KEY,
        timeout_seconds=5.0,
        transport=httpx.MockTransport(handler),
    )


class TestSupabaseStorageClient:
    async def test_upload_sends_correct_request(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["url"] = str(request.url)
            seen["apikey"] = request.headers.get("apikey")
            seen["auth"] = request.headers.get("authorization")
            seen["content_type"] = request.headers.get("content-type")
            seen["upsert"] = request.headers.get("x-upsert")
            seen["body"] = request.content
            return httpx.Response(200, json={"Key": "resumes/u/r.pdf"})

        await _client(handler).upload_object(
            bucket="resumes",
            path="user-id/resume-id.pdf",
            content=b"%PDF-data",
            content_type="application/pdf",
            access_token=_TOKEN,
        )
        assert seen["method"] == "POST"
        assert seen["url"] == (
            f"{_SUPABASE_URL}/storage/v1/object/resumes/user-id/resume-id.pdf"
        )
        assert seen["apikey"] == _ANON_KEY
        assert seen["auth"] == f"Bearer {_TOKEN}"  # caller's own JWT, not a service key
        assert seen["content_type"] == "application/pdf"
        assert seen["upsert"] == "false"
        assert seen["body"] == b"%PDF-data"

    async def test_upload_failure_raises_storage_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, json={"error": "denied"})

        with pytest.raises(StorageOperationError):
            await _client(handler).upload_object(
                bucket="resumes",
                path="a/b.pdf",
                content=b"x",
                content_type="application/pdf",
                access_token=_TOKEN,
            )

    async def test_download_returns_bytes(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            return httpx.Response(200, content=b"%PDF-bytes")

        content = await _client(handler).download_object(
            bucket="resumes", path="a/b.pdf", access_token=_TOKEN
        )
        assert content == b"%PDF-bytes"

    async def test_download_missing_object_raises_not_found(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "not found"})

        with pytest.raises(StorageObjectNotFoundError):
            await _client(handler).download_object(
                bucket="resumes", path="a/b.pdf", access_token=_TOKEN
            )

    async def test_delete_tolerates_missing_object(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "not found"})

        await _client(handler).delete_object(
            bucket="resumes", path="a/b.pdf", access_token=_TOKEN
        )

    async def test_signed_url_built_from_response(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path.endswith("/object/sign/resumes/a/b.pdf")
            return httpx.Response(200, json={"signedURL": "/object/sign/resumes/a/b.pdf?token=t"})

        url = await _client(handler).create_signed_url(
            bucket="resumes", path="a/b.pdf", expires_in_seconds=300, access_token=_TOKEN
        )
        assert url == f"{_SUPABASE_URL}/storage/v1/object/sign/resumes/a/b.pdf?token=t"

    async def test_transport_failure_raises_storage_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom")

        with pytest.raises(StorageOperationError):
            await _client(handler).download_object(
                bucket="resumes", path="a/b.pdf", access_token=_TOKEN
            )


class TestSlidingWindowRateLimiter:
    def test_allows_up_to_max_then_blocks(self) -> None:
        limiter = SlidingWindowRateLimiter(max_events=3, window_seconds=60)
        key = uuid.uuid4()
        for i in range(3):
            limiter.check(key, now=100.0 + i)
        with pytest.raises(RateLimitedError):
            limiter.check(key, now=104.0)

    def test_window_slides(self) -> None:
        limiter = SlidingWindowRateLimiter(max_events=2, window_seconds=60)
        key = uuid.uuid4()
        limiter.check(key, now=0.0)
        limiter.check(key, now=1.0)
        with pytest.raises(RateLimitedError):
            limiter.check(key, now=30.0)
        limiter.check(key, now=61.5)  # first event expired

    def test_keys_are_independent(self) -> None:
        limiter = SlidingWindowRateLimiter(max_events=1, window_seconds=60)
        key_a, key_b = uuid.uuid4(), uuid.uuid4()
        limiter.check(key_a, now=0.0)
        limiter.check(key_b, now=0.0)
        with pytest.raises(RateLimitedError):
            limiter.check(key_a, now=1.0)

    def test_retry_after_reported(self) -> None:
        limiter = SlidingWindowRateLimiter(max_events=1, window_seconds=60)
        key = uuid.uuid4()
        limiter.check(key, now=0.0)
        with pytest.raises(RateLimitedError) as excinfo:
            limiter.check(key, now=10.0)
        assert excinfo.value.details["retry_after_seconds"] >= 1
