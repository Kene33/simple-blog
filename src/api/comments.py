from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, get_optional_auth, require_unmuted_csrf
from src.modules.comments.schemas import CommentCreateRequest, CommentPage, CommentRead, CommentUpdateRequest
from src.modules.comments.service import create_comment, delete_comment, get_comment, list_comments, serialize_comments, update_comment

router = APIRouter(tags=["comments"])


@router.post("/api/v1/posts/{post_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def create(post_id: UUID, payload: CommentCreateRequest, request: Request, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> CommentRead:
    await request.app.state.rate_limiter.check(request, "comment-create", 30, 600, str(auth.user.id))
    await request.app.state.rate_limiter.check(request, "comment-create", 60, 600)
    comment = await create_comment(session, post_id, auth.user, payload)
    await session.commit()
    await session.refresh(comment)
    return (await serialize_comments(session, [comment]))[0]


@router.get("/api/v1/posts/{post_id}/comments", response_model=CommentPage)
async def list_for_post(post_id: UUID, parent_id: UUID | None = None, cursor: str | None = None, limit: int = 20, auth: CurrentAuth | None = Depends(get_optional_auth), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> CommentPage:
    return await list_comments(session, settings=settings, post_id=post_id, parent_id=parent_id, cursor=cursor, limit=min(max(limit, 1), 100), viewer_id=auth.user.id if auth else None)


@router.get("/api/v1/comments/{comment_id}", response_model=CommentRead)
async def read(comment_id: UUID, auth: CurrentAuth | None = Depends(get_optional_auth), session: AsyncSession = Depends(get_session)) -> CommentRead:
    return (await serialize_comments(session, [await get_comment(session, comment_id, viewer_id=auth.user.id if auth else None)]))[0]


@router.patch("/api/v1/comments/{comment_id}", response_model=CommentRead)
async def update(comment_id: UUID, payload: CommentUpdateRequest, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> CommentRead:
    comment = await update_comment(session, await get_comment(session, comment_id, owner_id=auth.user.id, viewer_id=auth.user.id), payload)
    await session.commit()
    await session.refresh(comment)
    return (await serialize_comments(session, [comment]))[0]


@router.delete("/api/v1/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def remove(comment_id: UUID, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    await delete_comment(session, await get_comment(session, comment_id, owner_id=auth.user.id, viewer_id=auth.user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
