from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.db.models import Post, PostLike, ShareEvent, User
from src.modules.interactions.schemas import LikeRead, ShareCreateRequest, ShareRead
from src.modules.posts.service import get_post


async def like_post(session: AsyncSession, post_id: UUID, user: User) -> LikeRead:
    post = await get_post(session, post_id)
    if session.bind and session.bind.dialect.name == "postgresql":
        result = await session.execute(postgresql_insert(PostLike).values(post_id=post_id, user_id=user.id).on_conflict_do_nothing())
        created = result.rowcount == 1
    else:
        existing = await session.get(PostLike, {"post_id": post_id, "user_id": user.id})
        created = existing is None
        if created:
            session.add(PostLike(post_id=post_id, user_id=user.id))
            await session.flush()
    if created:
        await session.execute(update(Post).where(Post.id == post_id).values(like_count=Post.like_count + 1))
    await session.refresh(post)
    return LikeRead(post_id=post.id, like_count=post.like_count, liked_by_me=True)


async def unlike_post(session: AsyncSession, post_id: UUID, user: User) -> None:
    await get_post(session, post_id)
    result = await session.execute(delete(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == user.id))
    if result.rowcount:
        await session.execute(update(Post).where(Post.id == post_id, Post.like_count > 0).values(like_count=Post.like_count - 1))


async def record_share(session: AsyncSession, post_id: UUID, user: User | None, payload: ShareCreateRequest, settings: Settings) -> ShareRead:
    post = await get_post(session, post_id)
    session.add(ShareEvent(post_id=post_id, user_id=user.id if user else None, channel=payload.channel))
    await session.flush()
    await session.execute(update(Post).where(Post.id == post_id).values(share_count=Post.share_count + 1))
    await session.refresh(post)
    return ShareRead(post_id=post.id, canonical_url=f"{settings.public_base_url.rstrip('/')}/posts/{post.id}", share_count=post.share_count)
