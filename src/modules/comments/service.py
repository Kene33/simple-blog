import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.db.models import Comment, Post, User
from src.modules.auth.service import user_summary
from src.modules.comments.schemas import CommentCreateRequest, CommentPage, CommentRead
from src.modules.posts.service import get_post

TOMBSTONE_BODY = "[deleted]"


def _scope(post_id: UUID, parent_id: UUID | None) -> str:
    return hashlib.sha256(f"{post_id}:{parent_id}".encode()).hexdigest()


def _encode_cursor(comment: Comment, scope: str, settings: Settings) -> str:
    payload = {"v": 1, "resource": "comments", "created_at": comment.created_at.isoformat(), "id": str(comment.id), "scope": scope}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_cursor(value: str, scope: str, settings: Settings) -> tuple[datetime, UUID]:
    try:
        encoded, signature = value.split(".", 1)
        expected = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["v"] != 1 or payload["resource"] != "comments" or payload["scope"] != scope:
            raise ValueError
        return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None


async def create_comment(session: AsyncSession, post_id: UUID, author: User, payload: CommentCreateRequest) -> Comment:
    await get_post(session, post_id)
    if payload.parent_id is not None:
        parent = await session.scalar(select(Comment).where(Comment.id == payload.parent_id, Comment.post_id == post_id))
        if parent is None:
            raise AppError("VALIDATION_ERROR", "Parent comment must belong to this post", 422)
    now = datetime.now(timezone.utc)
    comment = Comment(post_id=post_id, author_id=author.id, parent_id=payload.parent_id, body=payload.body, created_at=now, updated_at=now)
    session.add(comment)
    await session.flush()
    await session.execute(update(Post).where(Post.id == post_id).values(comment_count=Post.comment_count + 1))
    return comment


async def get_comment(session: AsyncSession, comment_id: UUID, owner_id: UUID | None = None, include_deleted: bool = False) -> Comment:
    query = select(Comment).where(Comment.id == comment_id)
    if not include_deleted:
        query = query.where(Comment.deleted_at.is_(None))
    comment = await session.scalar(query)
    if comment is None or owner_id is not None and comment.author_id != owner_id:
        raise AppError("RESOURCE_NOT_FOUND", "Comment not found", 404)
    return comment


async def serialize_comments(session: AsyncSession, comments: list[Comment]) -> list[CommentRead]:
    if not comments:
        return []
    authors = {user.id: user for user in (await session.scalars(select(User).where(User.id.in_({comment.author_id for comment in comments})))).all()}
    return [CommentRead(id=comment.id, post_id=comment.post_id, author=user_summary(authors[comment.author_id]), parent_id=comment.parent_id, body=TOMBSTONE_BODY if comment.deleted_at else comment.body, is_deleted=comment.deleted_at is not None, created_at=comment.created_at, updated_at=comment.updated_at) for comment in comments]


async def list_comments(session: AsyncSession, *, settings: Settings, post_id: UUID, parent_id: UUID | None, cursor: str | None, limit: int) -> CommentPage:
    await get_post(session, post_id)
    scope = _scope(post_id, parent_id)
    query = select(Comment).where(Comment.post_id == post_id, Comment.parent_id == parent_id)
    sqlite_cursor_id: UUID | None = None
    if cursor:
        created_at, comment_id = _decode_cursor(cursor, scope, settings)
        if session.bind and session.bind.dialect.name == "postgresql":
            query = query.where((Comment.created_at > created_at) | ((Comment.created_at == created_at) & (Comment.id > comment_id)))
        else:
            sqlite_cursor_id = comment_id
    rows = (await session.scalars(query.order_by(Comment.created_at, Comment.id))).all() if sqlite_cursor_id else (await session.scalars(query.order_by(Comment.created_at, Comment.id).limit(limit + 1))).all()
    if sqlite_cursor_id:
        try:
            rows = rows[[comment.id for comment in rows].index(sqlite_cursor_id) + 1 : limit + 2]
        except ValueError:
            raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None
    next_cursor = _encode_cursor(rows[limit - 1], scope, settings) if len(rows) > limit else None
    return CommentPage(items=await serialize_comments(session, rows[:limit]), next_cursor=next_cursor)
