"""Profile routes.

``GET /profiles/me`` is the first protected route in Caviar and exists to
demonstrate the full Phase 2 authentication + ownership + RLS chain
working end to end: a verified JWT resolves an ``AuthenticatedUser``, an
RLS-bound DB session is derived from it, and the profile service
auto-provisions the caller's own ``profiles`` row on first access.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthenticatedUser, get_current_user
from app.db.rls import get_authenticated_db
from app.schemas.profile import ProfileResponse
from app.services.profiles.service import get_or_create_profile

router = APIRouter()


@router.get("/profiles/me", response_model=ProfileResponse)
async def get_my_profile(
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_authenticated_db),
) -> ProfileResponse:
    profile = await get_or_create_profile(db, user.id)
    return ProfileResponse.model_validate(profile)
