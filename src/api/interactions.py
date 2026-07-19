from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, optional_csrf, require_csrf
from src.modules.interactions.schemas import LikeRead, ShareCreateRequest, ShareRead
from src.modules.interactions.service import like_post, record_share, unlike_post

router = APIRouter(prefix="/api/v1/posts", tags=["interactions"])


@router.put("/{post_id}/like", response_model=LikeRead)
async def like(post_id: UUID, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> LikeRead:
    result = await like_post(session, post_id, auth.user)
    await session.commit()
    return result


@router.delete("/{post_id}/like", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def unlike(post_id: UUID, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    await unlike_post(session, post_id, auth.user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{post_id}/shares", response_model=ShareRead, status_code=status.HTTP_201_CREATED)
async def share(post_id: UUID, payload: ShareCreateRequest, auth: CurrentAuth | None = Depends(optional_csrf), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> ShareRead:
    result = await record_share(session, post_id, auth.user if auth else None, payload, settings)
    await session.commit()
    return result
