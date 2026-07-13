"""Supabase Storage integration.

All object operations go through the Supabase Storage REST API
(``/storage/v1/object/...``) - the sanctioned access path. Caviar
application code never reads or writes ``storage.objects`` metadata rows
directly; that table is owned and managed by Supabase's storage-api
service, and manipulating it directly would desynchronize the object
metadata from the actual stored bytes.

Authorization model: every call carries
  * ``apikey``: the project's anon (publishable) key - required by the
    Storage API on every request, and
  * ``Authorization: Bearer <caller's own verified JWT>`` - so the
    Storage RLS policies from migration 0004 (first path segment must
    equal ``auth.uid()``) are enforced by Supabase itself on every
    operation. Even a backend path-construction bug therefore cannot
    read or write another user's objects. The service-role key is
    deliberately not used (and not configured) in this phase.

``StorageClient`` is a Protocol so the resume service depends on an
interface, not on httpx - tests and future providers substitute an
implementation without touching orchestration code.
"""

from __future__ import annotations

import logging
from typing import Protocol
from urllib.parse import quote

import httpx
from fastapi import Depends

from app.config import Settings, get_settings
from app.core.exceptions import AppError, NotFoundError, UpstreamServiceError

logger = logging.getLogger(__name__)


class StorageConfigurationError(AppError):
    """Raised when Supabase Storage settings are missing. Operator error
    (HTTP 500), mirroring AuthConfigurationError's rationale."""

    status_code = 500
    error_code = "storage_misconfigured"


class StorageOperationError(UpstreamServiceError):
    """A Storage API call failed in a way the caller cannot fix by
    changing their request (network failure, 5xx, timeout)."""

    error_code = "storage_unavailable"


class StorageObjectNotFoundError(NotFoundError):
    error_code = "storage_object_not_found"


class StorageClient(Protocol):
    """The storage operations the resume pipeline needs. Implementations
    must enforce that ``access_token`` is the acting user's verified JWT."""

    async def upload_object(
        self, *, bucket: str, path: str, content: bytes, content_type: str, access_token: str
    ) -> None: ...

    async def download_object(self, *, bucket: str, path: str, access_token: str) -> bytes: ...

    async def delete_object(self, *, bucket: str, path: str, access_token: str) -> None: ...

    async def create_signed_url(
        self, *, bucket: str, path: str, expires_in_seconds: int, access_token: str
    ) -> str: ...


class SupabaseStorageClient:
    """httpx-based implementation of ``StorageClient`` against the
    Supabase Storage REST API."""

    def __init__(
        self,
        *,
        supabase_url: str,
        anon_key: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = f"{supabase_url.rstrip('/')}/storage/v1"
        self._anon_key = anon_key
        self._timeout = timeout_seconds
        # Test seam: unit tests inject httpx.MockTransport; production
        # callers leave this None and httpx uses its real transport.
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    def _headers(self, access_token: str) -> dict[str, str]:
        return {
            "apikey": self._anon_key,
            "Authorization": f"Bearer {access_token}",
        }

    def _object_url(self, bucket: str, path: str) -> str:
        # Path segments are quoted individually; our canonical paths are
        # `{user_uuid}/{resume_uuid}.pdf` (no user-controlled characters),
        # but quoting is kept as defense-in-depth against future callers.
        quoted = "/".join(quote(segment, safe="") for segment in path.split("/"))
        return f"{self._base_url}/object/{bucket}/{quoted}"

    async def upload_object(
        self, *, bucket: str, path: str, content: bytes, content_type: str, access_token: str
    ) -> None:
        headers = self._headers(access_token)
        headers["Content-Type"] = content_type
        headers["x-upsert"] = "false"
        try:
            async with self._client() as client:
                response = await client.post(
                    self._object_url(bucket, path), headers=headers, content=content
                )
        except httpx.HTTPError as exc:
            logger.error("Storage upload transport failure: %s", exc.__class__.__name__)
            raise StorageOperationError("File storage is currently unavailable.") from exc
        if response.status_code not in (200, 201):
            logger.error(
                "Storage upload failed: status=%s bucket=%s", response.status_code, bucket
            )
            raise StorageOperationError("Failed to store the uploaded file.")

    async def download_object(self, *, bucket: str, path: str, access_token: str) -> bytes:
        try:
            async with self._client() as client:
                response = await client.get(
                    self._object_url(bucket, path), headers=self._headers(access_token)
                )
        except httpx.HTTPError as exc:
            logger.error("Storage download transport failure: %s", exc.__class__.__name__)
            raise StorageOperationError("File storage is currently unavailable.") from exc
        if response.status_code == 200:
            return response.content
        if response.status_code in (400, 404):
            raise StorageObjectNotFoundError("The stored file could not be found.")
        logger.error("Storage download failed: status=%s bucket=%s", response.status_code, bucket)
        raise StorageOperationError("Failed to retrieve the stored file.")

    async def delete_object(self, *, bucket: str, path: str, access_token: str) -> None:
        try:
            async with self._client() as client:
                response = await client.delete(
                    self._object_url(bucket, path), headers=self._headers(access_token)
                )
        except httpx.HTTPError as exc:
            logger.error("Storage delete transport failure: %s", exc.__class__.__name__)
            raise StorageOperationError("File storage is currently unavailable.") from exc
        # 404 on delete is treated as success: the desired end state (object
        # absent) already holds, and failing here would strand DB cleanup.
        if response.status_code not in (200, 204, 404):
            logger.error("Storage delete failed: status=%s bucket=%s", response.status_code, bucket)
            raise StorageOperationError("Failed to delete the stored file.")

    async def create_signed_url(
        self, *, bucket: str, path: str, expires_in_seconds: int, access_token: str
    ) -> str:
        quoted = "/".join(quote(segment, safe="") for segment in path.split("/"))
        sign_url = f"{self._base_url}/object/sign/{bucket}/{quoted}"
        try:
            async with self._client() as client:
                response = await client.post(
                    sign_url,
                    headers=self._headers(access_token),
                    json={"expiresIn": expires_in_seconds},
                )
        except httpx.HTTPError as exc:
            logger.error("Storage sign transport failure: %s", exc.__class__.__name__)
            raise StorageOperationError("File storage is currently unavailable.") from exc
        if response.status_code == 200:
            payload = response.json()
            signed_path = payload.get("signedURL") or payload.get("signedUrl")
            if not signed_path:
                logger.error("Storage sign response missing signedURL field.")
                raise StorageOperationError("Failed to create a download link.")
            return f"{self._base_url}{signed_path}"
        if response.status_code in (400, 404):
            raise StorageObjectNotFoundError("The stored file could not be found.")
        logger.error("Storage sign failed: status=%s bucket=%s", response.status_code, bucket)
        raise StorageOperationError("Failed to create a download link.")


def get_storage_client(settings: Settings = Depends(get_settings)) -> StorageClient:
    """FastAPI dependency producing the configured storage client. Tests
    and local development override this dependency with a fake."""
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise StorageConfigurationError(
            "Supabase Storage is not configured (set SUPABASE_URL and SUPABASE_ANON_KEY)."
        )
    return SupabaseStorageClient(
        supabase_url=settings.SUPABASE_URL,
        anon_key=settings.SUPABASE_ANON_KEY,
        timeout_seconds=settings.STORAGE_TIMEOUT_SECONDS,
    )
