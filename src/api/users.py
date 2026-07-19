from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.errors import AppError
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, get_current_auth, require_csrf
from src.modules.auth.schemas import PublicUserProfile, UserProfile, UserUpdateRequest
from src.modules.comments.schemas import CommentPage
from src.modules.comments.service import list_user_comments
from src.modules.users.service import find_public_user, profile_for_user, update_user

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
async def current_profile(auth: CurrentAuth = Depends(get_current_auth), session: AsyncSession = Depends(get_session)) -> UserProfile:
    return await profile_for_user(session, auth.user, include_private=True)


@router.patch("/me", response_model=UserProfile)
async def update_current_profile(payload: UserUpdateRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> UserProfile:
    try:
        user = await update_user(session, auth.user, payload)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise AppError("RESOURCE_CONFLICT", "Username or email is already in use", 409) from None
    await session.refresh(user)
    return await profile_for_user(session, user, include_private=True)


@router.get("/{username}", response_model=PublicUserProfile)
async def public_profile(username: str, session: AsyncSession = Depends(get_session)) -> PublicUserProfile:
    user = await find_public_user(session, username)
    return await profile_for_user(session, user, include_private=False)


@router.get("/{username}/comments", response_model=CommentPage)
async def public_comments(username: str, cursor: str | None = None, limit: int = 20, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> CommentPage:
    user = await find_public_user(session, username)
    return await list_user_comments(session, settings=settings, user_id=user.id, cursor=cursor, limit=min(max(limit, 1), 100))
