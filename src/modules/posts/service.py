import base64
import hashlib
import hmac
import json
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.db.models import Category, CategoryRequest, Media, Post, PostBookmark, PostLike, PostMedia, PostTag, Tag, User
from src.modules.auth.service import user_summary
from src.modules.categories.service import as_category, as_request, category_request_for, resolve_category_selection
from src.modules.media.service import as_read, replace_post_media
from src.modules.posts.schemas import DraftCreateRequest, DraftPage, DraftRead, DraftUpdateRequest, PostCreateRequest, PostPage, PostRead, PostUpdateRequest


def cursor_scope(*, author: str | None, category: str | None, tag: str | None, query_text: str | None, search_in: str, sort: str) -> str:
    value = json.dumps({"author": author, "category": category, "tag": tag, "query": query_text, "search_in": search_in, "sort": sort}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(value).hexdigest()


def encode_cursor(post: Post, scope: str, settings: Settings, resource: str = "posts", timestamp: str = "created_at") -> str:
    payload = {"v": 1, "resource": resource, "created_at": getattr(post, timestamp).isoformat(), "id": str(post.id), "scope": scope}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def decode_cursor(value: str, scope: str, settings: Settings, resource: str = "posts") -> tuple[datetime, UUID]:
    try:
        encoded, signature = value.split(".", 1)
        expected = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload["v"] != 1 or payload["resource"] != resource or payload["scope"] != scope:
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
            try:
                async with session.begin_nested():
                    tag = Tag(name=name, name_normalized=name)
                    session.add(tag)
                    await session.flush()
            except IntegrityError:
                tag = await session.scalar(select(Tag).where(Tag.name_normalized == name))
                if tag is None:
                    raise
            tags.append(tag)
    return tags


async def write_tags(session: AsyncSession, post: Post, names: list[str]) -> None:
    await session.execute(delete(PostTag).where(PostTag.post_id == post.id))
    for tag in await resolve_tags(session, names):
        session.add(PostTag(post_id=post.id, tag_id=tag.id))


async def create_post(session: AsyncSession, author: User, payload: PostCreateRequest) -> Post:
    now = datetime.now(timezone.utc)
    category, request = await resolve_category_selection(session, category_id=payload.category_id, category_request_id=payload.category_request_id, category_name=payload.category)
    post = Post(author_id=author.id, status="pending_category" if request else "published", title=payload.title, content=payload.content, category=category.name, category_id=category.id, category_request_id=request.id if request else None, created_at=now, updated_at=now)
    session.add(post)
    await session.flush()
    await write_tags(session, post, payload.tags)
    await replace_post_media(session, post.id, author.id, payload.media_ids)
    await session.flush()
    return post


async def create_draft(session: AsyncSession, author: User, payload: DraftCreateRequest) -> Post:
    now = datetime.now(timezone.utc)
    category, request = await resolve_category_selection(session, category_id=payload.category_id, category_request_id=payload.category_request_id, category_name=payload.category)
    draft = Post(author_id=author.id, status="draft", title=payload.title, content=payload.content, category=category.name, category_id=category.id, category_request_id=request.id if request else None, created_at=now, updated_at=now)
    session.add(draft)
    await session.flush()
    await write_tags(session, draft, payload.tags)
    await replace_post_media(session, draft.id, author.id, payload.media_ids)
    await session.flush()
    return draft


async def get_draft(session: AsyncSession, draft_id: UUID, owner_id: UUID) -> Post:
    draft = await session.scalar(select(Post).where(Post.id == draft_id, Post.author_id == owner_id, Post.status.in_(("draft", "needs_category_change")), Post.deleted_at.is_(None)))
    if draft is None:
        raise AppError("RESOURCE_NOT_FOUND", "Draft not found", 404)
    return draft


async def serialize_draft(session: AsyncSession, draft: Post) -> DraftRead:
    post = (await serialize_posts(session, [draft]))[0]
    request, _ = await category_request_for(session, draft.category_request_id)
    return DraftRead(id=post.id, author=post.author, title=post.title, content=post.content, category=post.category, category_request=post.category_request, tags=post.tags, media=post.media, status=draft.status, category_resolution=request.resolution if request else None, created_at=post.created_at, updated_at=post.updated_at)


async def list_drafts(session: AsyncSession, *, settings: Settings, author_id: UUID, cursor: str | None, limit: int) -> DraftPage:
    scope = "drafts"
    query = select(Post).where(Post.author_id == author_id, Post.status.in_(("draft", "needs_category_change")), Post.deleted_at.is_(None))
    if cursor:
        updated_at, draft_id = decode_cursor(cursor, scope, settings, resource="drafts")
        query = query.where((Post.updated_at > updated_at) | ((Post.updated_at == updated_at) & (Post.id > draft_id)))
    drafts = (await session.scalars(query.order_by(Post.updated_at, Post.id).limit(limit + 1))).all()
    next_cursor = encode_cursor(drafts[limit - 1], scope, settings, resource="drafts", timestamp="updated_at") if len(drafts) > limit else None
    return DraftPage(items=[await serialize_draft(session, draft) for draft in drafts[:limit]], next_cursor=next_cursor)


async def update_draft(session: AsyncSession, draft: Post, author_id: UUID, payload: DraftUpdateRequest) -> Post:
    if not payload.has_changes():
        raise AppError("VALIDATION_ERROR", "At least one field must be provided", 422)
    for field in ("title", "content"):
        if field in payload.model_fields_set:
            setattr(draft, field, getattr(payload, field) or "")
    if {"category_id", "category_request_id", "category"} & payload.model_fields_set:
        category, request = await resolve_category_selection(session, category_id=payload.category_id, category_request_id=payload.category_request_id, category_name=payload.category)
        draft.category = category.name
        draft.category_id = category.id
        draft.category_request_id = request.id if request else None
        draft.status = "draft"
    if "tags" in payload.model_fields_set:
        await write_tags(session, draft, payload.tags or [])
    if "media_ids" in payload.model_fields_set:
        await replace_post_media(session, draft.id, author_id, payload.media_ids or [])
    draft.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return draft


async def publish_draft(session: AsyncSession, draft: Post) -> Post:
    if not draft.title.strip() or not draft.content.strip() or draft.category_id is None:
        raise AppError("VALIDATION_ERROR", "Draft requires title, content, and category before publishing", 422)
    category = await session.get(Category, draft.category_id)
    request, _ = await category_request_for(session, draft.category_request_id)
    if category is None:
        raise AppError("VALIDATION_ERROR", "Draft category is missing", 422)
    if request is not None:
        if request.status != "pending":
            raise AppError("RESOURCE_CONFLICT", "Category request is no longer pending", 409)
        draft.status = "pending_category"
    elif category.status == "approved":
        draft.status = "published"
    else:
        raise AppError("RESOURCE_CONFLICT", "Category is no longer approved", 409)
    draft.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return draft


async def delete_draft(session: AsyncSession, draft: Post) -> None:
    await replace_post_media(session, draft.id, draft.author_id, [])
    draft.deleted_at = datetime.now(timezone.utc)
    draft.updated_at = draft.deleted_at
    await session.flush()


async def get_post(session: AsyncSession, post_id: UUID, owner_id: UUID | None = None) -> Post:
    query = select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))
    if owner_id is None:
        query = query.join(User, User.id == Post.author_id).where(Post.status == "published", User.posts_visibility == "public")
    else:
        query = query.where(Post.author_id == owner_id)
    post = await session.scalar(query)
    if post is None:
        raise AppError("RESOURCE_NOT_FOUND", "Post not found", 404)
    return post


async def change_post_counter(session: AsyncSession, post_id: UUID, counter: str, delta: int) -> int:
    fields = {"comment_count": Post.comment_count, "like_count": Post.like_count, "share_count": Post.share_count}
    field = fields.get(counter)
    if field is None:
        raise ValueError("Unsupported post counter")
    condition = field > 0 if delta < 0 else True
    await session.execute(update(Post).where(Post.id == post_id, condition).values({counter: field + delta}))
    return await read_post_counter(session, post_id, counter)


async def read_post_counter(session: AsyncSession, post_id: UUID, counter: str) -> int:
    fields = {"comment_count": Post.comment_count, "like_count": Post.like_count, "share_count": Post.share_count}
    field = fields.get(counter)
    if field is None:
        raise ValueError("Unsupported post counter")
    value = await session.scalar(select(field).where(Post.id == post_id))
    return value or 0


async def update_post(session: AsyncSession, post: Post, author_id: UUID, payload: PostUpdateRequest) -> Post:
    if not payload.has_changes():
        raise AppError("VALIDATION_ERROR", "At least one field must be provided", 422)
    for field in ("title", "content"):
        value = getattr(payload, field)
        if value is not None:
            setattr(post, field, value.strip())
    if {"category_id", "category_request_id", "category"} & payload.model_fields_set:
        category, request = await resolve_category_selection(session, category_id=payload.category_id, category_request_id=payload.category_request_id, category_name=payload.category)
        post.category = category.name
        post.category_id = category.id
        post.category_request_id = request.id if request else None
        post.status = "pending_category" if request else "published"
    if "tags" in payload.model_fields_set:
        await write_tags(session, post, payload.tags or [])
    if "media_ids" in payload.model_fields_set:
        await replace_post_media(session, post.id, author_id, payload.media_ids or [])
    post.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return post


async def serialize_post(session: AsyncSession, post: Post, viewer_id: UUID | None = None) -> PostRead:
    return (await serialize_posts(session, [post], viewer_id))[0]


async def serialize_posts(session: AsyncSession, posts: list[Post], viewer_id: UUID | None = None) -> list[PostRead]:
    if not posts:
        return []
    post_ids = [post.id for post in posts]
    author_ids = {post.author_id for post in posts}
    authors = {user.id: user for user in (await session.scalars(select(User).where(User.id.in_(author_ids)))).all()}
    categories = {category.id: category for category in (await session.scalars(select(Category).where(Category.id.in_({post.category_id for post in posts if post.category_id is not None})))).all()}
    requests = {request.id: request for request in (await session.scalars(select(CategoryRequest).where(CategoryRequest.id.in_({post.category_request_id for post in posts if post.category_request_id is not None})))).all()}
    tags_by_post: dict[UUID, list[str]] = defaultdict(list)
    for post_id, tag_name in (await session.execute(select(PostTag.post_id, Tag.name).join(Tag, Tag.id == PostTag.tag_id).where(PostTag.post_id.in_(post_ids)).order_by(Tag.name_normalized))).all():
        tags_by_post[post_id].append(tag_name)
    media_by_post: dict[UUID, list[Media]] = defaultdict(list)
    for post_id, media in (await session.execute(select(PostMedia.post_id, Media).join(Media, Media.id == PostMedia.media_id).where(PostMedia.post_id.in_(post_ids)).order_by(PostMedia.position))).all():
        media_by_post[post_id].append(media)
    liked_post_ids: set[UUID] = set()
    bookmarked_post_ids: set[UUID] = set()
    if viewer_id is not None:
        liked_post_ids = set((await session.scalars(select(PostLike.post_id).where(PostLike.post_id.in_(post_ids), PostLike.user_id == viewer_id))).all())
        bookmarked_post_ids = set((await session.scalars(select(PostBookmark.post_id).where(PostBookmark.post_id.in_(post_ids), PostBookmark.user_id == viewer_id))).all())
    return [
        PostRead(
            id=post.id,
            author=user_summary(authors[post.author_id]),
            title=post.title,
            content=post.content,
            category=as_category(categories.get(post.category_id)),
            category_request=as_request(requests.get(post.category_request_id), categories.get(post.category_id)),
            status=post.status,
            tags=tags_by_post[post.id],
            media=[as_read(media) for media in media_by_post[post.id]],
            like_count=post.like_count,
            comment_count=post.comment_count,
            share_count=post.share_count,
            liked_by_me=post.id in liked_post_ids,
            bookmarked_by_me=post.id in bookmarked_post_ids,
            created_at=post.created_at,
            updated_at=post.updated_at,
        )
        for post in posts
    ]


async def list_posts(session: AsyncSession, *, settings: Settings, author: str | None, category: str | None, tag: str | None, query_text: str | None, search_in: str, sort: str, cursor: str | None, limit: int, viewer_id: UUID | None = None) -> PostPage:
    visibility = or_(User.posts_visibility == "public", Post.author_id == viewer_id) if viewer_id is not None else User.posts_visibility == "public"
    query = select(Post).join(User, User.id == Post.author_id).where(Post.status == "published", Post.deleted_at.is_(None), visibility)
    if author:
        query = query.where(User.username_normalized == author.casefold())
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
        compare = Post.id < post_id if sort == "newest" else Post.id > post_id
        time_compare = Post.created_at < created_at if sort == "newest" else Post.created_at > created_at
        query = query.where(time_compare | ((Post.created_at == created_at) & compare))
    rows = (await session.scalars(query.order_by(*order).limit(limit + 1))).all()
    next_cursor = encode_cursor(rows[limit - 1], scope, settings) if len(rows) > limit else None
    return PostPage(items=await serialize_posts(session, rows[:limit], viewer_id), next_cursor=next_cursor)
