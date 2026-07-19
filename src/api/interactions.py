from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, require_csrf
from src.modules.interactions.schemas import LikeRead
from src.modules.interactions.service import like_post, unlike_post

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
