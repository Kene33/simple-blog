from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, require_csrf
from src.modules.comments.schemas import CommentCreateRequest, CommentPage, CommentRead
from src.modules.comments.service import create_comment, get_comment, list_comments, serialize_comments

router = APIRouter(tags=["comments"])


@router.post("/api/v1/posts/{post_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def create(post_id: UUID, payload: CommentCreateRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> CommentRead:
    comment = await create_comment(session, post_id, auth.user, payload)
    await session.commit()
    await session.refresh(comment)
    return (await serialize_comments(session, [comment]))[0]


@router.get("/api/v1/posts/{post_id}/comments", response_model=CommentPage)
async def list_for_post(post_id: UUID, parent_id: UUID | None = None, cursor: str | None = None, limit: int = 20, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> CommentPage:
    return await list_comments(session, settings=settings, post_id=post_id, parent_id=parent_id, cursor=cursor, limit=min(max(limit, 1), 100))


@router.get("/api/v1/comments/{comment_id}", response_model=CommentRead)
async def read(comment_id: UUID, session: AsyncSession = Depends(get_session)) -> CommentRead:
    return (await serialize_comments(session, [await get_comment(session, comment_id)]))[0]
