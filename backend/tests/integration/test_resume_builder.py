"""Integration tests for Phase 6 Resume Builder against a real, migrated
Postgres with RLS enforced. Conventions match the Phase 4/5 integration
suites (DB-availability skip, auth.users provisioning, HS256 test tokens,
shared autouse engine disposal, scripted fake Gemini raw client behind
the real StructuredAIRunner).

Proven here beyond the unit suite:
  1. Full CRUD + structured-section lifecycle over real JSONB storage,
     with the one-section-per-type invariant (migration 0008) exercised
     via upsert.
  2. Invalid section content is rejected with per-field details and
     nothing persisted.
  3. Cross-user isolation for projects, sections, and assistance.
  4. The assist flow end to end: prompt carries trust-wrapped user
     content, strict output validation, deterministic fabrication-guard
     warnings on an invented number, persistence-free behavior, and
     typed failure propagation (503 on provider failure, 422 on
     unimprovable requests).
"""

from __future__ import annotations

import json
import time
import uuid

import jwt as pyjwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.services.ai.client import StructuredAIRunner, get_ai_runner
from app.services.ai.exceptions import AIProviderUnavailableError

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


class ScriptedRawClient:
    def __init__(self, script: list) -> None:
        self.script = script  # live reference; tests append after setup
        self.calls: list[dict] = []

    async def generate_raw(self, **kwargs) -> str:
        self.calls.append(kwargs)
        behavior = self.script.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


@pytest_asyncio.fixture
async def db_engine():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            migrated = (
                await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = "
                        "'uq_resume_builder_sections_type')"
                    )
                )
            ).scalar_one()
    except Exception:
        await engine.dispose()
        pytest.skip("Database unreachable - integration tests skipped.")
    if not migrated:
        await engine.dispose()
        pytest.skip("Schema not migrated to 0008 - run `alembic upgrade head` first.")
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
def monkeypatch_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_JWKS_URL", None)
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "integration-test-gemini-key")
    return settings


@pytest.fixture
def ai_script():
    return []


@pytest_asyncio.fixture
async def client(monkeypatch_settings, ai_script):
    from app.main import app

    raw_client = ScriptedRawClient(ai_script)
    app.dependency_overrides[get_ai_runner] = lambda: StructuredAIRunner(
        raw_client, monkeypatch_settings
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac.raw_ai = raw_client  # type: ignore[attr-defined]
            yield ac
    finally:
        app.dependency_overrides.pop(get_ai_runner, None)


async def _provision(client: AsyncClient, user_id: uuid.UUID) -> None:
    response = await client.get("/api/v1/profiles/me", headers=_auth(user_id))
    assert response.status_code == 200


async def _create_project(client: AsyncClient, user_id: uuid.UUID, title: str) -> str:
    response = await client.post(
        "/api/v1/resume-builder/projects", headers=_auth(user_id), json={"title": title}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


EXPERIENCE_CONTENT = {
    "entries": [
        {
            "company": "Example Corp",
            "title": "Software Engineering Intern",
            "start_date": "May 2024",
            "end_date": "Aug 2024",
            "bullets": ["Built an async ingestion service handling 500 requests per minute"],
        }
    ]
}

SKILLS_CONTENT = {"groups": [{"name": "Languages", "skills": ["Python", "C++"]}]}


class TestBuilderCrud:
    async def test_project_and_section_lifecycle(self, client, two_users) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        project_id = await _create_project(client, user_a, "SWE Resume")

        # Upsert two sections; re-upsert one (update path of the
        # one-per-type invariant).
        put = await client.put(
            f"/api/v1/resume-builder/projects/{project_id}/sections/EXPERIENCE",
            headers=_auth(user_a),
            json={"content": EXPERIENCE_CONTENT},
        )
        assert put.status_code == 200, put.text
        assert put.json()["sort_order"] == 4
        put2 = await client.put(
            f"/api/v1/resume-builder/projects/{project_id}/sections/SKILLS",
            headers=_auth(user_a),
            json={"content": SKILLS_CONTENT},
        )
        assert put2.status_code == 200
        updated = dict(EXPERIENCE_CONTENT)
        updated["entries"] = [dict(EXPERIENCE_CONTENT["entries"][0], title="SWE Intern")]
        put3 = await client.put(
            f"/api/v1/resume-builder/projects/{project_id}/sections/EXPERIENCE",
            headers=_auth(user_a),
            json={"content": updated},
        )
        assert put3.status_code == 200
        assert put3.json()["id"] == put.json()["id"]  # updated, not duplicated

        detail = await client.get(
            f"/api/v1/resume-builder/projects/{project_id}", headers=_auth(user_a)
        )
        body = detail.json()
        assert body["title"] == "SWE Resume"
        assert [s["section_type"] for s in body["sections"]] == ["SKILLS", "EXPERIENCE"]
        experience = body["sections"][1]
        assert experience["content"]["entries"][0]["title"] == "SWE Intern"

        # PATCH project; DELETE section; DELETE project.
        patched = await client.patch(
            f"/api/v1/resume-builder/projects/{project_id}",
            headers=_auth(user_a),
            json={"status": "FINALIZED"},
        )
        assert patched.json()["status"] == "FINALIZED"
        deleted_section = await client.delete(
            f"/api/v1/resume-builder/projects/{project_id}/sections/SKILLS",
            headers=_auth(user_a),
        )
        assert deleted_section.status_code == 204
        missing = await client.delete(
            f"/api/v1/resume-builder/projects/{project_id}/sections/SKILLS",
            headers=_auth(user_a),
        )
        assert missing.status_code == 404
        deleted_project = await client.delete(
            f"/api/v1/resume-builder/projects/{project_id}", headers=_auth(user_a)
        )
        assert deleted_project.status_code == 204
        listing = await client.get("/api/v1/resume-builder/projects", headers=_auth(user_a))
        assert listing.json()["projects"] == []

    async def test_invalid_section_content_rejected_with_details(
        self, client, two_users
    ) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        project_id = await _create_project(client, user_a, "Draft")
        response = await client.put(
            f"/api/v1/resume-builder/projects/{project_id}/sections/SUMMARY",
            headers=_auth(user_a),
            json={"content": {"text": "ok", "font": "Comic Sans"}},
        )
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "invalid_section_content"
        assert any("font" in item["field"] for item in error["details"]["errors"])
        detail = await client.get(
            f"/api/v1/resume-builder/projects/{project_id}", headers=_auth(user_a)
        )
        assert detail.json()["sections"] == []  # nothing persisted

    async def test_cross_user_isolation(self, client, two_users) -> None:
        user_a, user_b = two_users
        await _provision(client, user_a)
        await _provision(client, user_b)
        project_id = await _create_project(client, user_a, "Private")
        for method, url, kwargs in [
            ("get", f"/api/v1/resume-builder/projects/{project_id}", {}),
            (
                "patch",
                f"/api/v1/resume-builder/projects/{project_id}",
                {"json": {"title": "Hijacked"}},
            ),
            ("delete", f"/api/v1/resume-builder/projects/{project_id}", {}),
            (
                "put",
                f"/api/v1/resume-builder/projects/{project_id}/sections/SKILLS",
                {"json": {"content": SKILLS_CONTENT}},
            ),
            (
                "post",
                f"/api/v1/resume-builder/projects/{project_id}/assist",
                {"json": {"assist_type": "GENERATE_SUMMARY"}},
            ),
        ]:
            response = await getattr(client, method)(url, headers=_auth(user_b), **kwargs)
            assert response.status_code == 404, (method, url, response.text)


class TestContentAssistance:
    async def test_bullets_assist_full_flow_with_fabrication_guard(
        self, client, two_users, ai_script
    ) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        project_id = await _create_project(client, user_a, "SWE Resume")
        await client.put(
            f"/api/v1/resume-builder/projects/{project_id}/sections/EXPERIENCE",
            headers=_auth(user_a),
            json={"content": EXPERIENCE_CONTENT},
        )

        ai_script.append(
            json.dumps(
                {
                    "bullets": [
                        {
                            "original": (
                                "Built an async ingestion service handling 500 "
                                "requests per minute"
                            ),
                            "improved": (
                                "Engineered an async ingestion service sustaining 500 "
                                "requests per minute, cutting latency by 40%"
                            ),
                            "changes_explained": ["Stronger action verb"],
                            "missing_fact_questions": [
                                "What latency reduction did you actually measure?"
                            ],
                        }
                    ],
                    "action_verb_suggestions": ["Engineered", "Architected"],
                }
            )
        )
        response = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/assist",
            headers=_auth(user_a),
            json={
                "assist_type": "IMPROVE_BULLETS",
                "section_type": "EXPERIENCE",
                "entry_index": 0,
                "target_role": "Backend Engineer",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["schema_version"] == "content-assist-1.0.0"
        bullet = body["bullets"][0]
        # 500 is user-stated -> supported; 40 was invented by the fake AI
        # -> deterministically flagged by the backend guard.
        assert bullet["unsupported_numbers"] == ["40"]
        assert bullet["missing_fact_questions"]

        # Trust boundary: user content and target role reached the model
        # wrapped, with the anti-fabrication system rules.
        sent = client.raw_ai.calls[0]
        assert sent["user_content"].count("BEGIN_UNTRUSTED_CONTENT[") == 3
        assert "Never fabricate" in sent["system_instruction"]

        # Persistence-free: stored content is unchanged.
        detail = await client.get(
            f"/api/v1/resume-builder/projects/{project_id}", headers=_auth(user_a)
        )
        stored = detail.json()["sections"][0]["content"]["entries"][0]["bullets"][0]
        assert stored == EXPERIENCE_CONTENT["entries"][0]["bullets"][0]

    async def test_summary_generation_requires_grounding_content(
        self, client, two_users, ai_script
    ) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        project_id = await _create_project(client, user_a, "Empty")
        response = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/assist",
            headers=_auth(user_a),
            json={"assist_type": "GENERATE_SUMMARY"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "assist_request_invalid"
        assert client.raw_ai.calls == []  # AI never contacted without facts

    async def test_summary_assist_flow(self, client, two_users, ai_script) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        project_id = await _create_project(client, user_a, "SWE Resume")
        await client.put(
            f"/api/v1/resume-builder/projects/{project_id}/sections/SKILLS",
            headers=_auth(user_a),
            json={"content": SKILLS_CONTENT},
        )
        ai_script.append(
            json.dumps(
                {
                    "improved_summary": "Backend engineer skilled in Python and C++.",
                    "changes_explained": ["Grounded in listed skills"],
                    "missing_fact_questions": [],
                    "action_verb_suggestions": [],
                }
            )
        )
        response = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/assist",
            headers=_auth(user_a),
            json={"assist_type": "GENERATE_SUMMARY"},
        )
        assert response.status_code == 200
        assert response.json()["unsupported_numbers"] == []

    async def test_assist_error_paths(self, client, two_users, ai_script) -> None:
        user_a, _ = two_users
        await _provision(client, user_a)
        project_id = await _create_project(client, user_a, "SWE Resume")
        await client.put(
            f"/api/v1/resume-builder/projects/{project_id}/sections/EXPERIENCE",
            headers=_auth(user_a),
            json={"content": EXPERIENCE_CONTENT},
        )

        # Missing parameters for IMPROVE_BULLETS.
        response = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/assist",
            headers=_auth(user_a),
            json={"assist_type": "IMPROVE_BULLETS"},
        )
        assert response.status_code == 422

        # Non-bullet section type.
        response = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/assist",
            headers=_auth(user_a),
            json={"assist_type": "IMPROVE_BULLETS", "section_type": "SKILLS", "entry_index": 0},
        )
        assert response.status_code == 422

        # Out-of-range entry index.
        response = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/assist",
            headers=_auth(user_a),
            json={
                "assist_type": "IMPROVE_BULLETS",
                "section_type": "EXPERIENCE",
                "entry_index": 5,
            },
        )
        assert response.status_code == 422

        # Transient provider failure -> 503, typed error code, retried once.
        ai_script.extend(
            [AIProviderUnavailableError("down"), AIProviderUnavailableError("down")]
        )
        response = await client.post(
            f"/api/v1/resume-builder/projects/{project_id}/assist",
            headers=_auth(user_a),
            json={
                "assist_type": "IMPROVE_BULLETS",
                "section_type": "EXPERIENCE",
                "entry_index": 0,
            },
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ai_unavailable"
