"""The ownership model's entry point: every authenticated user gets
exactly one ``profiles`` row, keyed by their verified Supabase Auth user
id. There is no separate "sign up" endpoint in this backend - Supabase
Auth owns account creation entirely; this service just ensures a profile
row exists the first time an authenticated user is seen by our backend.

Every function here takes the acting user's id as an explicit parameter
sourced from the verified JWT (``AuthenticatedUser.id``), never from a
request body/query/path parameter, per the ownership model mandated by
Phase 0 Draft 2.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.profile import Profile


async def get_or_create_profile(db: AsyncSession, user_id: uuid.UUID) -> Profile:
    result = await db.execute(select(Profile).where(Profile.id == user_id))
    profile = result.scalar_one_or_none()
    if profile is not None:
        return profile

    profile = Profile(id=user_id)
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile
