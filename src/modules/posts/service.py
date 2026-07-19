import base64
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import String, cast, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import AppError
from src.db.models import Media, Post, PostMedia, PostTag, Tag, User
from src.modules.auth.service import user_summary
from src.modules.posts.schemas import PostCreateRequest, PostPage, PostRead, PostUpdateRequest


def encode_cursor(post: Post) -> str:
    value = json.dumps({"created_at": post.created_at.isoformat(), "id": str(post.id)}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, UUID]:
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None


async def resolve_tags(session: AsyncSession, names: list[str]) -> list[Tag]:
    if not names:
        return []
    existing = {tag.name_normalized: tag for tag in (await session.scalars(select(Tag).where(Tag.name_normalized.in_(names)))).all()}
    tags = list(existing.values())
    for name in names:
        if name not in existing:
            tag = Tag(name=name, name_normalized=name)
            session.add(tag)
            tags.append(tag)
    await session.flush()
    return tags


async def attach_media(session: AsyncSession, post: Post, owner_id: UUID, media_ids: list[UUID]) -> None:
    if not media_ids:
        return
    media = (await session.scalars(select(Media).where(Media.id.in_(media_ids), Media.owner_id == owner_id, Media.deleted_at.is_(None)))).all()
    if len(media) != len(media_ids) or len([item for item in media if item.kind == "video"]) > 1:
        raise AppError("VALIDATION_ERROR", "Media must be active, owned, and include at most one video", 422)
    for position, media_id in enumerate(media_ids):
        session.add(PostMedia(post_id=post.id, media_id=media_id, position=position))


async def write_tags(session: AsyncSession, post: Post, names: list[str]) -> None:
    await session.execute(delete(PostTag).where(PostTag.post_id == post.id))
    for tag in await resolve_tags(session, names):
        session.add(PostTag(post_id=post.id, tag_id=tag.id))


async def create_post(session: AsyncSession, author: User, payload: PostCreateRequest) -> Post:
    now = datetime.now(timezone.utc)
    post = Post(author_id=author.id, title=payload.title, content=payload.content, category=payload.category, created_at=now, updated_at=now)
    session.add(post)
    await session.flush()
    await write_tags(session, post, payload.tags)
    await attach_media(session, post, author.id, payload.media_ids)
    await session.flush()
    return post


async def get_post(session: AsyncSession, post_id: UUID, owner_id: UUID | None = None) -> Post:
    post = await session.scalar(select(Post).where(Post.id == post_id, Post.deleted_at.is_(None)))
    if post is None or owner_id is not None and post.author_id != owner_id:
        raise AppError("RESOURCE_NOT_FOUND", "Post not found", 404)
    return post


async def update_post(session: AsyncSession, post: Post, author_id: UUID, payload: PostUpdateRequest) -> Post:
    if not payload.has_changes():
        raise AppError("VALIDATION_ERROR", "At least one field must be provided", 422)
    for field in ("title", "content", "category"):
        value = getattr(payload, field)
        if value is not None:
            setattr(post, field, value.strip())
    if "tags" in payload.model_fields_set:
        await write_tags(session, post, payload.tags or [])
    if "media_ids" in payload.model_fields_set:
        await session.execute(delete(PostMedia).where(PostMedia.post_id == post.id))
        await attach_media(session, post, author_id, payload.media_ids or [])
    await session.flush()
    return post


async def serialize_post(session: AsyncSession, post: Post) -> PostRead:
    author = await session.get(User, post.author_id)
    tags = (await session.scalars(select(Tag.name).join(PostTag, PostTag.tag_id == Tag.id).where(PostTag.post_id == post.id))).all()
    media = (await session.scalars(select(Media).join(PostMedia, PostMedia.media_id == Media.id).where(PostMedia.post_id == post.id).order_by(PostMedia.position))).all()
    return PostRead(id=post.id, author=user_summary(author), title=post.title, content=post.content, category=post.category or "", tags=list(tags), media=[{"id": item.id, "kind": item.kind, "mime_type": item.mime_type, "url": f"/api/v1/media/{item.id}"} for item in media], like_count=post.like_count, comment_count=post.comment_count, share_count=post.share_count, created_at=post.created_at, updated_at=post.updated_at)


async def list_posts(session: AsyncSession, *, author: str | None, category: str | None, tag: str | None, cursor: str | None, limit: int) -> PostPage:
    query = select(Post).where(Post.deleted_at.is_(None)).order_by(Post.created_at.desc(), Post.id.desc())
    if author:
        query = query.join(User, User.id == Post.author_id).where(User.username_normalized == author.casefold())
    if category:
        query = query.where(Post.category == category)
    if tag:
        query = query.join(PostTag, PostTag.post_id == Post.id).join(Tag, Tag.id == PostTag.tag_id).where(Tag.name_normalized == tag.casefold())
    if cursor:
        created_at, post_id = decode_cursor(cursor)
        query = query.where((Post.created_at < created_at) | ((Post.created_at == created_at) & (cast(Post.id, String) < str(post_id))))
    rows = (await session.scalars(query.limit(limit + 1))).all()
    next_cursor = encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return PostPage(items=[await serialize_post(session, post) for post in rows[:limit]], next_cursor=next_cursor)
