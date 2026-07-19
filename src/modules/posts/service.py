import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import String, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import AppError
from src.core.config import Settings
from src.db.models import Media, Post, PostMedia, PostTag, Tag, User
from src.modules.auth.service import user_summary
from src.modules.posts.schemas import PostCreateRequest, PostPage, PostRead, PostUpdateRequest


def cursor_scope(*, author: str | None, category: str | None, tag: str | None, query_text: str | None, search_in: str, sort: str) -> str:
    value = json.dumps({"author": author, "category": category, "tag": tag, "query": query_text, "search_in": search_in, "sort": sort}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def encode_cursor(post: Post, scope: str, settings: Settings) -> str:
    payload = {"v": 1, "resource": "posts", "created_at": post.created_at.isoformat(), "id": str(post.id), "scope": scope}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def decode_cursor(value: str, scope: str, settings: Settings) -> tuple[datetime, UUID]:
    try:
        encoded, signature = value.split(".", 1)
        expected = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload["v"] != 1 or payload["resource"] != "posts" or payload["scope"] != scope:
            raise ValueError
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
    media = (await session.scalars(select(Media).where(Media.id.in_(media_ids), Media.owner_id == owner_id, Media.status == "uploaded", Media.deleted_at.is_(None)))).all()
    if len(media) != len(media_ids) or len([item for item in media if item.kind == "video"]) > 1:
        raise AppError("VALIDATION_ERROR", "Media must be active, owned, and include at most one video", 422)
    for position, media_id in enumerate(media_ids):
        session.add(PostMedia(post_id=post.id, media_id=media_id, position=position))
    now = datetime.now(timezone.utc)
    for item in media:
        item.status = "attached"
        item.attached_at = now


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
        previous_media = (await session.scalars(select(Media).join(PostMedia, PostMedia.media_id == Media.id).where(PostMedia.post_id == post.id))).all()
        await session.execute(delete(PostMedia).where(PostMedia.post_id == post.id))
        for item in previous_media:
            item.status = "uploaded"
            item.attached_at = None
        await attach_media(session, post, author_id, payload.media_ids or [])
    await session.flush()
    return post


async def serialize_post(session: AsyncSession, post: Post) -> PostRead:
    author = await session.get(User, post.author_id)
    tags = (await session.scalars(select(Tag.name).join(PostTag, PostTag.tag_id == Tag.id).where(PostTag.post_id == post.id))).all()
    media = (await session.scalars(select(Media).join(PostMedia, PostMedia.media_id == Media.id).where(PostMedia.post_id == post.id).order_by(PostMedia.position))).all()
    return PostRead(id=post.id, author=user_summary(author), title=post.title, content=post.content, category=post.category or "", tags=list(tags), media=[{"id": item.id, "kind": item.kind, "mime_type": item.mime_type, "url": f"/api/v1/media/{item.id}"} for item in media], like_count=post.like_count, comment_count=post.comment_count, share_count=post.share_count, created_at=post.created_at, updated_at=post.updated_at)


async def list_posts(session: AsyncSession, *, settings: Settings, author: str | None, category: str | None, tag: str | None, query_text: str | None, search_in: str, sort: str, cursor: str | None, limit: int) -> PostPage:
    query = select(Post).where(Post.deleted_at.is_(None))
    if author:
        query = query.join(User, User.id == Post.author_id).where(User.username_normalized == author.casefold())
    if category:
        query = query.where(Post.category == category)
    if tag:
        query = query.join(PostTag, PostTag.post_id == Post.id).join(Tag, Tag.id == PostTag.tag_id).where(Tag.name_normalized == tag.casefold())
    if query_text:
        if search_in not in {"all", "title", "content"}:
            raise AppError("VALIDATION_ERROR", "search_in must be all, title, or content", 422)
        if session.bind and session.bind.dialect.name == "postgresql":
            document = func.to_tsvector("simple", Post.title + " " + Post.content) if search_in == "all" else func.to_tsvector("simple", getattr(Post, search_in))
            query = query.where(document.op("@@")(func.plainto_tsquery("simple", query_text)))
        else:
            pattern = f"%{query_text}%"
            fields = [Post.title, Post.content] if search_in == "all" else [getattr(Post, search_in)]
            query = query.where(or_(*(field.ilike(pattern) for field in fields)))
    if sort not in {"newest", "oldest"}:
        raise AppError("VALIDATION_ERROR", "sort must be newest or oldest", 422)
    order = (Post.created_at.desc(), Post.id.desc()) if sort == "newest" else (Post.created_at.asc(), Post.id.asc())
    scope = cursor_scope(author=author, category=category, tag=tag, query_text=query_text, search_in=search_in, sort=sort)
    if cursor:
        created_at, post_id = decode_cursor(cursor, scope, settings)
        compare = cast(Post.id, String) < str(post_id) if sort == "newest" else cast(Post.id, String) > str(post_id)
        time_compare = Post.created_at < created_at if sort == "newest" else Post.created_at > created_at
        query = query.where(time_compare | ((Post.created_at == created_at) & compare))
    rows = (await session.scalars(query.order_by(*order).limit(limit + 1))).all()
    next_cursor = encode_cursor(rows[limit - 1], scope, settings) if len(rows) > limit else None
    return PostPage(items=[await serialize_post(session, post) for post in rows[:limit]], next_cursor=next_cursor)
