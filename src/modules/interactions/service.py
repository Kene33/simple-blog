from uuid import UUID

from sqlalchemy import delete, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Post, PostLike, User
from src.modules.interactions.schemas import LikeRead
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
