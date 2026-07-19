from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, require_csrf
from src.modules.posts.schemas import PostCreateRequest, PostPage, PostRead, PostUpdateRequest
from src.modules.posts.service import create_post, get_post, list_posts, serialize_post, update_post

router = APIRouter(prefix="/api/v1/posts", tags=["posts"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PostRead)
async def create(payload: PostCreateRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> PostRead:
    post = await create_post(session, auth.user, payload)
    await session.commit()
    await session.refresh(post)
    return await serialize_post(session, post)


@router.get("", response_model=PostPage)
async def list_feed(author: str | None = None, category: str | None = None, tag: str | None = None, query: str | None = None, search_in: str = "all", sort: str = "newest", cursor: str | None = None, limit: int = 20, session: AsyncSession = Depends(get_session)) -> PostPage:
    return await list_posts(session, author=author, category=category, tag=tag, query_text=query, search_in=search_in, sort=sort, cursor=cursor, limit=min(max(limit, 1), 100))


@router.get("/{post_id}", response_model=PostRead)
async def read(post_id: UUID, session: AsyncSession = Depends(get_session)) -> PostRead:
    return await serialize_post(session, await get_post(session, post_id))


@router.patch("/{post_id}", response_model=PostRead)
async def update(post_id: UUID, payload: PostUpdateRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> PostRead:
    post = await update_post(session, await get_post(session, post_id, auth.user.id), auth.user.id, payload)
    await session.commit()
    await session.refresh(post)
    return await serialize_post(session, post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_post(post_id: UUID, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    post = await get_post(session, post_id, auth.user.id)
    from datetime import datetime, timezone
    post.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
