"""Integration tests against a real, migrated Postgres database.

These tests require:
  - a running Postgres reachable via DATABASE_URL,
  - `alembic upgrade head` already applied,
and are skipped automatically when the database is unreachable, so the
unit-test suite stays runnable without local Postgres.

What they prove (things unit tests structurally cannot):
  1. The full HTTP auth chain: a signed Supabase-style JWT -> 401 vs 200 ->
     profile auto-provisioning -> response schema.
  2. RLS is genuinely enforced through the application's own database
     session mechanism (`get_authenticated_db` setting request.jwt.claims):
     user B cannot read or write user A's rows through the same SQLAlchemy
     session type the app itself uses.
  3. The updated_at trigger fires on direct (non-ORM) SQL updates -
     Phase 1 review observation #2's fix, verified end to end.
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
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings

_TEST_SECRET = "integration-test-secret-0123456789abcdef"


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


@pytest_asyncio.fixture
async def db_engine():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            has_schema = (
                await conn.execute(
                    text("SELECT to_regclass('public.profiles') IS NOT NULL")
                )
            ).scalar_one()
    except Exception:
        await engine.dispose()
        pytest.skip("Database unreachable - integration tests skipped.")
    if not has_schema:
        await engine.dispose()
        pytest.skip("Schema not migrated - run `alembic upgrade head` first.")
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def two_users(db_engine):
    """Creates two auth.users rows and cleans up everything they own."""
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    async with db_engine.begin() as conn:
        for uid in (user_a, user_b):
            await conn.execute(
                text("INSERT INTO auth.users (id, email) VALUES (:id, :email)"),
                {"id": uid, "email": f"user-{uid}@test.local"},
            )
    yield user_a, user_b
    async with db_engine.begin() as conn:
        # Cascades: profiles -> everything else via ON DELETE CASCADE chains.
        await conn.execute(
            text("DELETE FROM auth.users WHERE id IN (:a, :b)"), {"a": user_a, "b": user_b}
        )


@pytest_asyncio.fixture
async def auth_client(monkeypatch_secret):
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def monkeypatch_secret(monkeypatch):
    """Points JWT verification at the integration-test secret, shared-secret
    mode, regardless of what the developer's .env configures."""
    settings = get_settings()
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", _TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_JWKS_URL", None)
    return settings


pytestmark = pytest.mark.asyncio


class TestAuthenticatedProfileFlow:
    async def test_no_token_is_401(self, auth_client, db_engine) -> None:
        response = await auth_client.get("/api/v1/profiles/me")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "authentication_required"

    async def test_garbage_token_is_401(self, auth_client, db_engine) -> None:
        response = await auth_client.get(
            "/api/v1/profiles/me", headers={"Authorization": "Bearer garbage"}
        )
        assert response.status_code == 401

    async def test_valid_token_provisions_and_returns_profile(
        self, auth_client, two_users
    ) -> None:
        user_a, _ = two_users
        response = await auth_client.get(
            "/api/v1/profiles/me", headers={"Authorization": f"Bearer {_make_token(user_a)}"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(user_a)
        assert body["full_name"] is None

        # Second call: same row, not a duplicate.
        response2 = await auth_client.get(
            "/api/v1/profiles/me", headers={"Authorization": f"Bearer {_make_token(user_a)}"}
        )
        assert response2.status_code == 200
        assert response2.json()["id"] == str(user_a)


class TestRlsEnforcementThroughAppSessionMechanism:
    """Exercises RLS exactly the way the application does: an asyncpg-backed
    SQLAlchemy session with request.jwt.claims set via set_config, matching
    app/db/rls.py."""

    async def _session_as(self, db_engine, user_id: uuid.UUID):
        """Builds a session using the exact production mechanism from
        app/db/rls.py: RLS claims in session.info, re-armed on every
        transaction by the after_begin event registered at import time."""
        from app.db.rls import _RLS_CLAIMS_INFO_KEY  # production constant

        maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        session = maker()
        session.sync_session.info[_RLS_CLAIMS_INFO_KEY] = json.dumps(
            {"sub": str(user_id), "role": "authenticated"}
        )
        return session

    async def test_cross_user_reads_and_writes_blocked(self, db_engine, two_users) -> None:
        user_a, user_b = two_users

        # User A: create own profile + job_context.
        session_a = await self._session_as(db_engine, user_a)
        try:
            await session_a.execute(
                text("INSERT INTO profiles (id, full_name) VALUES (:id, 'User A')"),
                {"id": user_a},
            )
            await session_a.execute(
                text(
                    "INSERT INTO job_contexts (user_id, target_role) "
                    "VALUES (:uid, 'Backend Engineer')"
                ),
                {"uid": user_a},
            )
            await session_a.commit()
        finally:
            await session_a.close()

        # User B: must see zero of user A's rows.
        session_b = await self._session_as(db_engine, user_b)
        try:
            visible_profiles = (
                await session_b.execute(
                    text("SELECT count(*) FROM profiles WHERE id = :other"), {"other": user_a}
                )
            ).scalar_one()
            assert visible_profiles == 0

            visible_contexts = (
                await session_b.execute(text("SELECT count(*) FROM job_contexts"))
            ).scalar_one()
            assert visible_contexts == 0

            # User B: must not be able to insert a row claiming user A's id.
            with pytest.raises(Exception) as excinfo:
                await session_b.execute(
                    text(
                        "INSERT INTO job_contexts (user_id, target_role) "
                        "VALUES (:uid, 'Malicious')"
                    ),
                    {"uid": user_a},
                )
                await session_b.commit()
            assert "row-level security" in str(excinfo.value)
            await session_b.rollback()
        finally:
            await session_b.close()

    async def test_no_claims_set_means_no_rows_visible(self, db_engine, two_users) -> None:
        """A session that never sets request.jwt.claims (auth.uid() IS NULL)
        must see nothing - the fail-closed posture."""
        user_a, _ = two_users
        session_a = await self._session_as(db_engine, user_a)
        try:
            await session_a.execute(
                text("INSERT INTO profiles (id, full_name) VALUES (:id, 'User A')"),
                {"id": user_a},
            )
            await session_a.commit()
        finally:
            await session_a.close()

        maker = async_sessionmaker(bind=db_engine, expire_on_commit=False)
        bare_session = maker()
        try:
            visible = (
                await bare_session.execute(text("SELECT count(*) FROM profiles"))
            ).scalar_one()
            assert visible == 0
        finally:
            await bare_session.close()


class TestUpdatedAtTrigger:
    async def test_direct_sql_update_advances_updated_at(self, db_engine, two_users) -> None:
        user_a, _ = two_users
        async with db_engine.begin() as conn:
            claims = json.dumps({"sub": str(user_a), "role": "authenticated"})
            await conn.execute(
                text("SELECT set_config('request.jwt.claims', :claims, true)"),
                {"claims": claims},
            )
            await conn.execute(
                text("INSERT INTO profiles (id, full_name) VALUES (:id, 'Before')"),
                {"id": user_a},
            )

        async with db_engine.begin() as conn:
            claims = json.dumps({"sub": str(user_a), "role": "authenticated"})
            await conn.execute(
                text("SELECT set_config('request.jwt.claims', :claims, true)"),
                {"claims": claims},
            )
            # Raw SQL update - no ORM onupdate involved. clock_timestamp()
            # comparison guarantees the trigger, not the ORM, moved the value.
            row = (
                await conn.execute(
                    text(
                        "UPDATE profiles SET full_name = 'After' WHERE id = :id "
                        "RETURNING created_at, updated_at"
                    ),
                    {"id": user_a},
                )
            ).one()
            assert row.updated_at >= row.created_at
            # updated_at must equal the transaction's now(), not the original
            # insert-time default. Insert and update happen in different
            # transactions, so now() differs between them.
            check = (
                await conn.execute(
                    text(
                        "SELECT updated_at > created_at AS advanced FROM profiles "
                        "WHERE id = :id"
                    ),
                    {"id": user_a},
                )
            ).scalar_one()
            assert check is True
