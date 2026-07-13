"""Binds the authenticated user's identity to the DB session so Postgres
Row Level Security actually applies to the backend's own queries - not
only to some hypothetical future direct-client access path.

Background: Supabase's real ``auth.uid()`` reads the ``request.jwt.claims``
Postgres setting, which Supabase's own PostgREST layer populates per
request from the verified JWT. Our FastAPI backend connects directly via
asyncpg, bypassing PostgREST entirely, so nothing sets that value unless
we do it ourselves.

Why an event hook instead of a single ``SET`` at dependency time: the
claims are applied with ``set_config(..., is_local => true)``, which is
*transaction*-scoped - deliberately, so the value can never leak across
pooled connections shared by concurrent requests. But transaction scope
also means every ``commit()`` wipes it, and SQLAlchemy may even check out
a different pooled connection for the next transaction in the same
session. Setting the claims once at the start of the request is therefore
not enough (verified by integration test: a post-commit ``refresh()`` in
the same request ran with ``auth.uid() IS NULL`` and RLS correctly hid the
caller's own just-committed row). The correct mechanism is a session
``after_begin`` event that re-arms the claims at the start of *every*
transaction the request's session opens, reading the caller's identity
from ``session.info`` (per-session state, set by the dependency below).
"""

from __future__ import annotations

import json

from fastapi import Depends
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app.core.security import AuthenticatedUser, get_current_user
from app.db.session import get_db

_RLS_CLAIMS_INFO_KEY = "caviar_rls_claims"


@event.listens_for(SyncSession, "after_begin")
def _apply_rls_claims_on_transaction_begin(session, transaction, connection) -> None:
    """Fires at the start of every transaction for every ORM session in the
    process. For sessions carrying RLS claims in ``session.info`` (i.e.
    sessions produced by ``get_authenticated_db``), sets the
    transaction-local ``request.jwt.claims`` so ``auth.uid()`` resolves to
    the authenticated caller for all statements in that transaction.
    Sessions without the info key (background jobs, tests that want the
    fail-closed behavior) are untouched and run with ``auth.uid() IS NULL``
    - meaning RLS denies them everything, which is the safe default."""
    claims = session.info.get(_RLS_CLAIMS_INFO_KEY)
    if claims is not None:
        connection.execute(
            text("SELECT set_config('request.jwt.claims', :claims, true)"),
            {"claims": claims},
        )


async def get_authenticated_db(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AsyncSession:
    """FastAPI dependency: an AsyncSession that applies the authenticated
    caller's identity to every transaction it opens for the rest of the
    request, so RLS policies keyed on ``auth.uid()`` evaluate correctly
    for every query - including queries in fresh transactions after a
    ``commit()``."""
    db.sync_session.info[_RLS_CLAIMS_INFO_KEY] = json.dumps(
        {"sub": str(user.id), "role": "authenticated"}
    )
    return db
