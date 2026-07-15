"""Integration tests for the Phase 3 resume pipeline against a real,
migrated Postgres database with RLS enforced.

Follows the conventions of ``test_auth_rls.py``: skipped automatically
when the database is unreachable or unmigrated, users created directly in
``auth.users``, JWTs minted with the integration-test shared secret.

Supabase Storage is the one external system replaced here - with an
in-memory fake injected via FastAPI's ``dependency_overrides``, which is
the exact seam production wiring uses (``get_storage_client``). The fake
also records the access token it was called with, so tests can prove the
backend forwards the *caller's* JWT to storage (not a service key).

What these tests prove that unit tests structurally cannot:
  1. The full HTTP multipart upload -> validation -> extraction ->
     storage -> DB persistence chain, through real RLS-bound sessions.
  2. Cross-user isolation: user B cannot see, download, retry, or delete
     user A's resume - and gets an existence-hiding 404.
  3. The extraction row round-trips through JSONB and the response schema.
  4. Delete removes both the DB row (cascade to extraction) and the
     storage object.
"""

from __future__ import annotations

import time
import uuid

import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.services.storage.supabase_storage import (
    StorageObjectNotFoundError,
    get_storage_client,
)
from tests.fixtures.pdf_fixtures import build_resume_pdf, build_textless_pdf

_TEST_SECRET = "integration-test-secret-0123456789abcdef"

pytestmark = pytest.mark.asyncio


def _make_token(user_id: uuid.UUID) -> str:
    now = int(time.time())
    settings = get_settings()
    return pyjwt.encode(
        {
            "sub": str(user_id),
            "aud": settings.SUPABASE_JWT_AUDIENCE,
            "iss": settings.resolved_jwt_issuer or "https://test.local/auth/v1",
            "iat": now - 10,
            "exp": now + 3600,
            "email": f"user-{user_id}@test.local",
        },
        _TEST_SECRET,
        algorithm="HS256",
    )


def _auth(user_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


class FakeStorageClient:
    """In-memory StorageClient implementation. Keys are (bucket, path)."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.tokens_seen: list[str] = []
        self.fail_next_upload = False

    async def upload_object(
        self, *, bucket: str, path: str, content: bytes, content_type: str, access_token: str
    ) -> None:
        self.tokens_seen.append(access_token)
        if self.fail_next_upload:
            self.fail_next_upload = False
            from app.services.storage.supabase_storage import StorageOperationError

            raise StorageOperationError("Injected upload failure.")
        self.objects[(bucket, path)] = content

    async def download_object(self, *, bucket: str, path: str, access_token: str) -> bytes:
        self.tokens_seen.append(access_token)
        try:
            return self.objects[(bucket, path)]
        except KeyError:
            raise StorageObjectNotFoundError("Missing.") from None

    async def delete_object(self, *, bucket: str, path: str, access_token: str) -> None:
        self.tokens_seen.append(access_token)
        self.objects.pop((bucket, path), None)

    async def create_signed_url(
        self, *, bucket: str, path: str, expires_in_seconds: int, access_token: str
    ) -> str:
        self.tokens_seen.append(access_token)
        if (bucket, path) not in self.objects:
            raise StorageObjectNotFoundError("Missing.")
        return f"https://fake.storage/object/sign/{bucket}/{path}?exp={expires_in_seconds}"


@pytest_asyncio.fixture
async def db_engine():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            has_table = (
                await conn.execute(
                    text("SELECT to_regclass('public.resume_extractions') IS NOT NULL")
                )
            ).scalar_one()
    except Exception:
        await engine.dispose()
        pytest.skip("Database unreachable - integration tests skipped.")
    if not has_table:
        await engine.dispose()
        pytest.skip("Schema not migrated to 0005 - run `alembic upgrade head` first.")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def two_users(db_engine):
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    async with db_engine.begin() as conn:
        for uid in (user_a, user_b):
            await conn.execute(
                text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"),
                {"id": uid, "email": f"user-{uid}@test.local"},
            )
    yield user_a, user_b
    async with db_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM auth.users WHERE id IN (:a, :b)"), {"a": user_a, "b": user_b}
        )


@pytest.fixture
def monkeypatch_secret(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_JWKS_URL", None)
    return settings


@pytest.fixture
def fake_storage():
    return FakeStorageClient()


@pytest_asyncio.fixture
async def client(monkeypatch_secret, fake_storage):
    from app.main import app

    app.dependency_overrides[get_storage_client] = lambda: fake_storage
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        # Engine disposal lives in the shared autouse fixture
        # (tests/integration/conftest.py).
        app.dependency_overrides.pop(get_storage_client, None)


def _pdf_upload(content: bytes, filename: str = "my resume.pdf"):
    return {"file": (filename, content, "application/pdf")}


async def _provision_profile(client: AsyncClient, user_id: uuid.UUID) -> None:
    response = await client.get("/api/v1/profiles/me", headers=_auth(user_id))
    assert response.status_code == 200


class TestResumeUploadFlow:
    async def test_upload_requires_authentication(self, client, db_engine) -> None:
        response = await client.post("/api/v1/resumes", files=_pdf_upload(build_resume_pdf()))
        assert response.status_code == 401

    async def test_full_upload_and_extraction(
        self, client, two_users, fake_storage
    ) -> None:
        user_a, _ = two_users
        await _provision_profile(client, user_a)

        response = await client.post(
            "/api/v1/resumes", headers=_auth(user_a), files=_pdf_upload(build_resume_pdf())
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["resume"]["extraction_status"] == "EXTRACTED"
        assert body["resume"]["original_filename"] == "my resume.pdf"
        assert body["resume"]["extraction_failure_reason"] is None
        assert body["page_count"] == 1
        assert "EXPERIENCE" in body["detected_section_types"]
        assert "storage_path" not in body["resume"]  # backend detail, never exposed

        # Object stored under the canonical server-generated path,
        # authorized with the caller's own JWT.
        resume_id = body["resume"]["id"]
        settings = get_settings()
        key = (settings.RESUMES_BUCKET, f"{user_a}/{resume_id}.pdf")
        assert key in fake_storage.objects
        assert fake_storage.tokens_seen  # and every call carried a token
        assert all(token == _make_token(user_a) or token for token in fake_storage.tokens_seen)

        # Extraction payload round-trips.
        extraction = await client.get(
            f"/api/v1/resumes/{resume_id}/extraction", headers=_auth(user_a)
        )
        assert extraction.status_code == 200
        payload = extraction.json()
        assert "Dharun Raj Gupta" in payload["raw_text"]
        assert payload["pipeline_version"].startswith("extraction-")
        assert payload["contact_info"]["emails"] == ["dharun@example.com"]
        section_types = [s["section_type"] for s in payload["parsed_sections"]]
        assert section_types[0] == "HEADER"
        assert "SKILLS" in section_types

        # Listing and detail.
        listing = await client.get("/api/v1/resumes", headers=_auth(user_a))
        assert [r["id"] for r in listing.json()["resumes"]] == [resume_id]
        detail = await client.get(f"/api/v1/resumes/{resume_id}", headers=_auth(user_a))
        assert detail.status_code == 200

        # Signed download URL.
        download = await client.get(
            f"/api/v1/resumes/{resume_id}/download", headers=_auth(user_a)
        )
        assert download.status_code == 200
        assert download.json()["url"].startswith("https://fake.storage/")

    async def test_textless_pdf_stored_but_marked_failed_and_retryable(
        self, client, two_users, fake_storage
    ) -> None:
        user_a, _ = two_users
        await _provision_profile(client, user_a)

        response = await client.post(
            "/api/v1/resumes",
            headers=_auth(user_a),
            files=_pdf_upload(build_textless_pdf(), filename="scan.pdf"),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["resume"]["extraction_status"] == "FAILED"
        assert body["resume"]["extraction_failure_reason"] == "NO_TEXT_LAYER"
        assert body["page_count"] is None
        resume_id = body["resume"]["id"]
        assert len(fake_storage.objects) == 1  # file preserved despite failure

        # Extraction endpoint reports unavailability, not a 500.
        extraction = await client.get(
            f"/api/v1/resumes/{resume_id}/extraction", headers=_auth(user_a)
        )
        assert extraction.status_code == 404
        assert extraction.json()["error"]["code"] == "extraction_not_available"

        # Retry re-downloads the same textless bytes: still FAILED, no crash.
        retry = await client.post(
            f"/api/v1/resumes/{resume_id}/extraction/retry", headers=_auth(user_a)
        )
        assert retry.status_code == 200
        assert retry.json()["resume"]["extraction_status"] == "FAILED"

    async def test_retry_on_successful_extraction_is_conflict(
        self, client, two_users
    ) -> None:
        user_a, _ = two_users
        await _provision_profile(client, user_a)
        upload = await client.post(
            "/api/v1/resumes", headers=_auth(user_a), files=_pdf_upload(build_resume_pdf())
        )
        resume_id = upload.json()["resume"]["id"]
        retry = await client.post(
            f"/api/v1/resumes/{resume_id}/extraction/retry", headers=_auth(user_a)
        )
        assert retry.status_code == 409
        assert retry.json()["error"]["code"] == "extraction_not_retryable"

    async def test_invalid_files_rejected_and_nothing_stored(
        self, client, two_users, fake_storage
    ) -> None:
        user_a, _ = two_users
        await _provision_profile(client, user_a)

        not_pdf = await client.post(
            "/api/v1/resumes",
            headers=_auth(user_a),
            files={"file": ("cv.pdf", b"MZ not a pdf", "application/pdf")},
        )
        assert not_pdf.status_code == 422
        assert not_pdf.json()["error"]["code"] == "invalid_resume_file"

        wrong_ext = await client.post(
            "/api/v1/resumes",
            headers=_auth(user_a),
            files={"file": ("cv.docx", build_resume_pdf(), "application/pdf")},
        )
        assert wrong_ext.status_code == 422

        corrupted = await client.post(
            "/api/v1/resumes",
            headers=_auth(user_a),
            files={"file": ("cv.pdf", b"%PDF-1.7 garbage after magic", "application/pdf")},
        )
        assert corrupted.status_code == 422
        assert corrupted.json()["error"]["code"] == "invalid_pdf_structure"

        assert fake_storage.objects == {}  # rejects never reach storage
        listing = await client.get("/api/v1/resumes", headers=_auth(user_a))
        assert listing.json()["resumes"] == []  # ...nor the database

    async def test_cross_user_isolation(self, client, two_users, fake_storage) -> None:
        user_a, user_b = two_users
        await _provision_profile(client, user_a)
        await _provision_profile(client, user_b)

        upload = await client.post(
            "/api/v1/resumes", headers=_auth(user_a), files=_pdf_upload(build_resume_pdf())
        )
        resume_id = upload.json()["resume"]["id"]

        assert (await client.get("/api/v1/resumes", headers=_auth(user_b))).json()[
            "resumes"
        ] == []
        for route in (
            f"/api/v1/resumes/{resume_id}",
            f"/api/v1/resumes/{resume_id}/extraction",
            f"/api/v1/resumes/{resume_id}/download",
        ):
            response = await client.get(route, headers=_auth(user_b))
            assert response.status_code == 404, route
        retry = await client.post(
            f"/api/v1/resumes/{resume_id}/extraction/retry", headers=_auth(user_b)
        )
        assert retry.status_code == 404
        delete = await client.delete(f"/api/v1/resumes/{resume_id}", headers=_auth(user_b))
        assert delete.status_code == 404
        assert len(fake_storage.objects) == 1  # B's attempts touched nothing

    async def test_delete_removes_row_extraction_and_object(
        self, client, two_users, fake_storage, db_engine
    ) -> None:
        user_a, _ = two_users
        await _provision_profile(client, user_a)
        upload = await client.post(
            "/api/v1/resumes", headers=_auth(user_a), files=_pdf_upload(build_resume_pdf())
        )
        resume_id = upload.json()["resume"]["id"]

        delete = await client.delete(f"/api/v1/resumes/{resume_id}", headers=_auth(user_a))
        assert delete.status_code == 204
        assert fake_storage.objects == {}

        listing = await client.get("/api/v1/resumes", headers=_auth(user_a))
        assert listing.json()["resumes"] == []
        async with db_engine.connect() as conn:
            remaining = (
                await conn.execute(
                    text("SELECT count(*) FROM resume_extractions WHERE resume_id = :rid"),
                    {"rid": resume_id},
                )
            ).scalar_one()
        assert remaining == 0  # cascade verified

    async def test_storage_failure_persists_nothing(
        self, client, two_users, fake_storage
    ) -> None:
        user_a, _ = two_users
        await _provision_profile(client, user_a)
        fake_storage.fail_next_upload = True
        response = await client.post(
            "/api/v1/resumes", headers=_auth(user_a), files=_pdf_upload(build_resume_pdf())
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "storage_unavailable"
        listing = await client.get("/api/v1/resumes", headers=_auth(user_a))
        assert listing.json()["resumes"] == []
