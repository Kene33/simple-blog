from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.db.models import PostLike, ShareEvent, User
from src.modules.interactions.schemas import LikeRead, ShareCreateRequest, ShareRead
from src.modules.posts.service import change_post_counter, get_post, read_post_counter


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
        like_count = await change_post_counter(session, post_id, "like_count", 1)
    else:
        like_count = await read_post_counter(session, post_id, "like_count")
    return LikeRead(post_id=post.id, like_count=like_count, liked_by_me=True)


async def unlike_post(session: AsyncSession, post_id: UUID, user: User) -> None:
    await get_post(session, post_id)
    result = await session.execute(delete(PostLike).where(PostLike.post_id == post_id, PostLike.user_id == user.id))
    if result.rowcount:
        await change_post_counter(session, post_id, "like_count", -1)


async def record_share(session: AsyncSession, post_id: UUID, user: User | None, payload: ShareCreateRequest, settings: Settings) -> ShareRead:
    post = await get_post(session, post_id)
    session.add(ShareEvent(post_id=post_id, user_id=user.id if user else None, channel=payload.channel))
    await session.flush()
    share_count = await change_post_counter(session, post_id, "share_count", 1)
    return ShareRead(post_id=post.id, canonical_url=f"{settings.public_base_url.rstrip('/')}/posts/{post.id}", share_count=share_count)
