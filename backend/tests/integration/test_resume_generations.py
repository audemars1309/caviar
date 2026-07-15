"""Integration tests for Phase 7 resume generation against a real,
migrated Postgres with RLS enforced. Conventions match the earlier
integration suites. Two externals are replaced through their production
seams: Supabase Storage (in-memory fake via ``get_storage_client``) and
the Tectonic binary (a fake executable selected via
``settings.TECTONIC_BINARY_PATH`` - the real subprocess machinery runs).

Proven here beyond the unit suite:
  1. The full lifecycle over HTTP: PENDING -> ... -> COMPLETED with
     template id+version, page count, file size, compiler metadata, and
     the object stored in the private generated-resumes bucket under the
     caller's own JWT.
  2. Failure behavior: compiler failure -> FAILED / COMPILER with a
     sanitized reason, structured section data untouched, and a
     subsequent retry (a new generation) succeeding.
  3. Preconditions: missing PERSONAL_INFO -> 409; unknown template -> 404
     with no generation row created.
  4. Ownership isolation for generations and downloads.
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
from tests.fixtures.pdf_fixtures import build_resume_pdf

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
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.tokens_seen: list[str] = []

    async def upload_object(self, *, bucket, path, content, content_type, access_token) -> None:
        self.tokens_seen.append(access_token)
        self.objects[(bucket, path)] = content

    async def download_object(self, *, bucket, path, access_token) -> bytes:
        try:
            return self.objects[(bucket, path)]
        except KeyError:
            raise StorageObjectNotFoundError("Missing.") from None

    async def delete_object(self, *, bucket, path, access_token) -> None:
        self.objects.pop((bucket, path), None)

    async def create_signed_url(self, *, bucket, path, expires_in_seconds, access_token) -> str:
        if (bucket, path) not in self.objects:
            raise StorageObjectNotFoundError("Missing.")
        return f"https://fake.storage/{bucket}/{path}"


@pytest_asyncio.fixture
async def db_engine():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            migrated = (
                await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE "
                        "table_name = 'resume_generations' AND column_name = 'warnings')"
                    )
                )
            ).scalar_one()
    except Exception:
        await engine.dispose()
        pytest.skip("Database unreachable - integration tests skipped.")
    if not migrated:
        await engine.dispose()
        pytest.skip("Schema not migrated to 0009 - run `alembic upgrade head` first.")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def user_ids(db_engine):
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
def fake_tectonic(tmp_path, monkeypatch) -> dict:
    """A controllable fake compiler binary wired into settings. Behavior
    is switched by rewriting the script between requests."""
    pdf_path = tmp_path / "fixture.pdf"
    pdf_path.write_bytes(build_resume_pdf())
    monkeypatch.setenv("CAVIAR_FAKE_PDF", str(pdf_path))
    script = tmp_path / "fake-tectonic"

    def set_behavior(kind: str) -> None:
        if kind == "success":
            body = 'cp "$CAVIAR_FAKE_PDF" "$OUTDIR/main.pdf"\nexit 0\n'
        elif kind == "fail":
            body = 'echo "error: undefined control sequence" >&2\nexit 1\n'
        else:
            raise ValueError(kind)
        script.write_text(
            "#!/bin/sh\n"
            'if [ "$1" = "--version" ]; then echo "tectonic 0.15.0-fake"; exit 0; fi\n'
            'OUTDIR="$2"\n' + body,
            encoding="utf-8",
        )
        script.chmod(0o755)

    set_behavior("success")
    return {"path": str(script), "set_behavior": set_behavior}


@pytest.fixture
def monkeypatch_settings(monkeypatch, fake_tectonic):
    settings = get_settings()
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_JWKS_URL", None)
    monkeypatch.setattr(settings, "TECTONIC_BINARY_PATH", fake_tectonic["path"])
    return settings


@pytest.fixture
def fake_storage():
    return FakeStorageClient()


@pytest_asyncio.fixture
async def client(monkeypatch_settings, fake_storage):
    from app.main import app

    app.dependency_overrides[get_storage_client] = lambda: fake_storage
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.pop(get_storage_client, None)


PERSONAL = {"full_name": "Dharun Raj Gupta", "email": "dharun@example.com"}
EXPERIENCE = {
    "entries": [
        {
            "company": "Example Corp",
            "title": "SWE Intern",
            "bullets": ["Built things with C# & $500 budget, 100% on_time"],
        }
    ]
}


async def _provision(client: AsyncClient, user_id: uuid.UUID) -> None:
    assert (await client.get("/api/v1/profiles/me", headers=_auth(user_id))).status_code == 200


async def _make_ready_project(client: AsyncClient, user_id: uuid.UUID) -> str:
    project = await client.post(
        "/api/v1/resume-builder/projects", headers=_auth(user_id), json={"title": "CV"}
    )
    project_id = project.json()["id"]
    for section_type, content in (("PERSONAL_INFO", PERSONAL), ("EXPERIENCE", EXPERIENCE)):
        response = await client.put(
            f"/api/v1/resume-builder/projects/{project_id}/sections/{section_type}",
            headers=_auth(user_id),
            json={"content": content},
        )
        assert response.status_code == 200, response.text
    return project_id


class TestGenerationPipeline:
    async def test_templates_endpoint_lists_approved(self, client, user_ids) -> None:
        user_a, _ = user_ids
        await _provision(client, user_a)
        response = await client.get("/api/v1/resume-templates", headers=_auth(user_a))
        assert response.status_code == 200
        templates = response.json()["templates"]
        assert templates[0]["template_id"] == "caviar_classic"
        assert templates[0]["template_version"] == "1.0.0"

    async def test_full_generation_lifecycle(
        self, client, user_ids, fake_storage
    ) -> None:
        user_a, _ = user_ids
        await _provision(client, user_a)
        project_id = await _make_ready_project(client, user_a)

        response = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/generations",
            headers=_auth(user_a),
            json={"template_id": "caviar_classic"},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["status"] == "COMPLETED"
        assert body["template_id"] == "caviar_classic"
        assert body["template_version"] == "1.0.0"
        assert body["page_count"] == 1
        assert body["file_size_bytes"] > 0
        assert body["compiler_version"] == "tectonic 0.15.0-fake"
        assert body["failure_category"] is None
        assert "storage_path" not in body  # backend detail, never exposed

        # Stored in the private generated-resumes bucket at the canonical
        # path, authorized with the caller's own JWT.
        key = (
            get_settings().GENERATED_RESUMES_BUCKET,
            f"{user_a}/{body['id']}.pdf",
        )
        assert key in fake_storage.objects
        assert fake_storage.objects[key].startswith(b"%PDF-")
        assert fake_storage.tokens_seen and all(fake_storage.tokens_seen)

        # Detail, listing, download.
        detail = await client.get(
            f"/api/v1/resume-generations/{body['id']}", headers=_auth(user_a)
        )
        assert detail.status_code == 200
        listing = await client.get(
            f"/api/v1/resume-builder/projects/{project_id}/generations",
            headers=_auth(user_a),
        )
        assert [g["id"] for g in listing.json()["generations"]] == [body["id"]]
        download = await client.get(
            f"/api/v1/resume-generations/{body['id']}/download", headers=_auth(user_a)
        )
        assert download.status_code == 200
        assert download.json()["url"].startswith("https://fake.storage/generated-resumes/")

    async def test_compiler_failure_preserves_content_and_is_retryable(
        self, client, user_ids, fake_storage, fake_tectonic
    ) -> None:
        user_a, _ = user_ids
        await _provision(client, user_a)
        project_id = await _make_ready_project(client, user_a)

        fake_tectonic["set_behavior"]("fail")
        failed = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/generations",
            headers=_auth(user_a),
            json={"template_id": "caviar_classic"},
        )
        assert failed.status_code == 201
        body = failed.json()
        assert body["status"] == "FAILED"
        assert body["failure_category"] == "COMPILER"
        assert body["failure_reason"].startswith("COMPILER_FAILED:")
        assert "caviar-gen-" not in body["failure_reason"]  # sanitized
        assert fake_storage.objects == {}  # nothing stored

        # Structured resume data untouched by the failure.
        detail = await client.get(
            f"/api/v1/resume-builder/projects/{project_id}", headers=_auth(user_a)
        )
        assert len(detail.json()["sections"]) == 2

        # Deterministic retry: fix the deterministic problem (compiler),
        # POST a new generation. The failed row remains immutable history.
        fake_tectonic["set_behavior"]("success")
        retried = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/generations",
            headers=_auth(user_a),
            json={"template_id": "caviar_classic"},
        )
        assert retried.json()["status"] == "COMPLETED"
        listing = await client.get(
            f"/api/v1/resume-builder/projects/{project_id}/generations",
            headers=_auth(user_a),
        )
        statuses = sorted(g["status"] for g in listing.json()["generations"])
        assert statuses == ["COMPLETED", "FAILED"]

    async def test_preconditions(self, client, user_ids, db_engine) -> None:
        user_a, _ = user_ids
        await _provision(client, user_a)
        project = await client.post(
            "/api/v1/resume-builder/projects", headers=_auth(user_a), json={"title": "Empty"}
        )
        project_id = project.json()["id"]

        # No PERSONAL_INFO -> 409.
        response = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/generations",
            headers=_auth(user_a),
            json={"template_id": "caviar_classic"},
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "generation_not_possible"

        # Unknown template -> 404, and no generation row was created.
        ready_project = await _make_ready_project(client, user_a)
        response = await client.post(
            f"/api/v1/resume-builder/projects/{ready_project}/generations",
            headers=_auth(user_a),
            json={"template_id": "evil_template"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "template_not_found"
        listing = await client.get(
            f"/api/v1/resume-builder/projects/{ready_project}/generations",
            headers=_auth(user_a),
        )
        assert listing.json()["generations"] == []

    async def test_cross_user_isolation(self, client, user_ids, fake_storage) -> None:
        user_a, user_b = user_ids
        await _provision(client, user_a)
        await _provision(client, user_b)
        project_id = await _make_ready_project(client, user_a)
        generation = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/generations",
            headers=_auth(user_a),
            json={"template_id": "caviar_classic"},
        )
        generation_id = generation.json()["id"]

        for url in (
            f"/api/v1/resume-builder/projects/{project_id}/generations",
            f"/api/v1/resume-generations/{generation_id}",
            f"/api/v1/resume-generations/{generation_id}/download",
        ):
            response = await client.get(url, headers=_auth(user_b))
            assert response.status_code == 404, url
        foreign_create = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/generations",
            headers=_auth(user_b),
            json={"template_id": "caviar_classic"},
        )
        assert foreign_create.status_code == 404
