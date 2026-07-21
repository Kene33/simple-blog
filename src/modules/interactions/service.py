import base64
import hashlib
import hmac
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.db.models import Post, PostBookmark, PostLike, ShareEvent, User
from src.modules.interactions.schemas import LikeRead, ShareCreateRequest, ShareRead
from src.modules.posts.schemas import PostPage
from src.modules.posts.service import change_post_counter, get_post, read_post_counter, serialize_posts


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
    if user is None:
        session.add(ShareEvent(post_id=post_id, user_id=None, channel=payload.channel))
        await session.flush()
        share_count = await change_post_counter(session, post_id, "share_count", 1)
    elif session.bind and session.bind.dialect.name == "postgresql":
        result = await session.execute(postgresql_insert(ShareEvent).values(post_id=post_id, user_id=user.id, channel=payload.channel).on_conflict_do_nothing(index_elements=[ShareEvent.post_id, ShareEvent.user_id]))
        share_count = await change_post_counter(session, post_id, "share_count", 1) if result.rowcount == 1 else await read_post_counter(session, post_id, "share_count")
    elif await session.scalar(select(ShareEvent.id).where(ShareEvent.post_id == post_id, ShareEvent.user_id == user.id)) is None:
        session.add(ShareEvent(post_id=post_id, user_id=user.id, channel=payload.channel))
        await session.flush()
        share_count = await change_post_counter(session, post_id, "share_count", 1)
    else:
        share_count = await read_post_counter(session, post_id, "share_count")
    return ShareRead(post_id=post.id, canonical_url=f"{settings.public_base_url.rstrip('/')}/posts/{post.id}", share_count=share_count)


async def bookmark_post(session: AsyncSession, post_id: UUID, user: User) -> None:
    await get_post(session, post_id)
    if await session.get(PostBookmark, {"post_id": post_id, "user_id": user.id}) is None:
        session.add(PostBookmark(post_id=post_id, user_id=user.id))
        await session.flush()


async def unbookmark_post(session: AsyncSession, post_id: UUID, user: User) -> None:
    await get_post(session, post_id)
    await session.execute(delete(PostBookmark).where(PostBookmark.post_id == post_id, PostBookmark.user_id == user.id))


def _bookmark_scope() -> str:
    return hashlib.sha256(b"bookmarks").hexdigest()


def _encode_bookmark_cursor(post: Post, settings: Settings) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps({"v": 1, "resource": "bookmarks", "created_at": post.created_at.isoformat(), "id": str(post.id), "scope": _bookmark_scope()}, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_bookmark_cursor(value: str, settings: Settings) -> tuple[datetime, UUID]:
    try:
        encoded, signature = value.split(".", 1)
        expected = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["v"] != 1 or payload["resource"] != "bookmarks" or payload["scope"] != _bookmark_scope():
            raise ValueError
        return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None


async def list_bookmarks(session: AsyncSession, *, settings: Settings, user_id: UUID, cursor: str | None, limit: int) -> PostPage:
    query = select(Post).join(PostBookmark, PostBookmark.post_id == Post.id).where(PostBookmark.user_id == user_id, Post.status == "published", Post.deleted_at.is_(None))
    if cursor:
        created_at, post_id = _decode_bookmark_cursor(cursor, settings)
        query = query.where((Post.created_at < created_at) | ((Post.created_at == created_at) & (Post.id < post_id)))
    posts = (await session.scalars(query.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit + 1))).all()
    next_cursor = _encode_bookmark_cursor(posts[limit - 1], settings) if len(posts) > limit else None
    return PostPage(items=await serialize_posts(session, posts[:limit], user_id), next_cursor=next_cursor)
