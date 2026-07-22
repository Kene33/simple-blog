from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.db.models import Post, PostTag, Tag
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, get_optional_auth, require_unmuted_csrf
from src.modules.posts.schemas import PostCreateRequest, PostPage, PostRead, PostUpdateRequest, TrendingRead, TrendingTerm
from src.modules.posts.service import create_post, get_post, list_posts, serialize_post, serialize_posts, update_post

router = APIRouter(prefix="/api/v1/posts", tags=["posts"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=PostRead)
async def create(payload: PostCreateRequest, request: Request, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> PostRead:
    await request.app.state.rate_limiter.check(request, "post-create", 20, 3600, str(auth.user.id))
    await request.app.state.rate_limiter.check(request, "post-create", 30, 3600)
    post = await create_post(session, auth.user, payload)
    await session.commit()
    await session.refresh(post)
    return await serialize_post(session, post)


@router.get("", response_model=PostPage)
async def list_feed(request: Request, author: str | None = Query(default=None, max_length=30), category: str | None = Query(default=None, max_length=80), tag: str | None = Query(default=None, max_length=30), query: str | None = Query(default=None, max_length=200), search_in: str = "all", sort: str = "newest", cursor: str | None = None, limit: int = 20, auth: CurrentAuth | None = Depends(get_optional_auth), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> PostPage:
    if query:
        await request.app.state.rate_limiter.check(request, "post-search", 60, 60, str(auth.user.id) if auth else None)
    return await list_posts(session, settings=settings, author=author, category=category, tag=tag, query_text=query, search_in=search_in, sort=sort, cursor=cursor, limit=min(max(limit, 1), 100), viewer_id=auth.user.id if auth else None)


@router.get("/trending", response_model=TrendingRead)
async def trending(session: AsyncSession = Depends(get_session)) -> TrendingRead:
    since = datetime.now(timezone.utc) - timedelta(days=30)
    visible = (Post.status == "published", Post.deleted_at.is_(None), Post.created_at >= since)
    posts = (await session.scalars(select(Post).where(*visible).order_by(Post.like_count.desc(), Post.created_at.desc()).limit(3))).all()
    categories = (await session.execute(select(Post.category, func.count(Post.id)).where(*visible, Post.category.is_not(None)).group_by(Post.category).order_by(func.count(Post.id).desc(), Post.category).limit(3))).all()
    tags = (await session.execute(select(Tag.name, func.count(PostTag.post_id)).join(PostTag, PostTag.tag_id == Tag.id).join(Post, Post.id == PostTag.post_id).where(*visible).group_by(Tag.id, Tag.name).order_by(func.count(PostTag.post_id).desc(), Tag.name).limit(3))).all()
    return TrendingRead(posts=await serialize_posts(session, posts), categories=[TrendingTerm(name=name, count=count) for name, count in categories], tags=[TrendingTerm(name=name, count=count) for name, count in tags])


@router.get("/{post_id}", response_model=PostRead)
async def read(post_id: UUID, auth: CurrentAuth | None = Depends(get_optional_auth), session: AsyncSession = Depends(get_session)) -> PostRead:
    return await serialize_post(session, await get_post(session, post_id, viewer_id=auth.user.id if auth else None), auth.user.id if auth else None)


@router.patch("/{post_id}", response_model=PostRead)
async def update(post_id: UUID, payload: PostUpdateRequest, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> PostRead:
    post = await update_post(session, await get_post(session, post_id, auth.user.id), auth.user.id, payload)
    await session.commit()
    await session.refresh(post)
    return await serialize_post(session, post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_post(post_id: UUID, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    post = await get_post(session, post_id, auth.user.id)
    from datetime import datetime, timezone
    post.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
