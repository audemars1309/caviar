"""Shared integration-test fixtures.

The application's SQLAlchemy engine is module-level and pools asyncpg
connections that are bound to the event loop they were created on.
pytest-asyncio gives every test function its own loop, so any pooled
connection surviving a test can poison a later test with "Future attached
to a different loop" - nondeterministically, depending on pool checkout
order. Disposing the app engine after EVERY integration test (while its
loop is still current) makes cross-loop leakage structurally impossible,
for this module and every future integration module, without each test
file having to remember to do it.
"""

from __future__ import annotations

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def _dispose_app_engine_after_test():
    yield
    from app.db.session import engine as app_engine

    await app_engine.dispose()
