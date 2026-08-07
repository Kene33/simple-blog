import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.db.models import Comment, ModerationAction, PasswordResetToken, Post, PostBookmark, PostLike, RefreshSession, Report, ShareEvent, User
from src.modules.auth.service import user_summary
from src.modules.comments.service import get_comment
from src.modules.moderation.schemas import (
    AdminUserRead,
    ModerationActionPage,
    ModerationActionRead,
    ReportCount,
    ReportCreateRequest,
    ReportPage,
    ReportRead,
    ReportTarget,
    ReportUpdateRequest,
    UserModerationRequest,
    UserRoleRequest,
)
from src.modules.posts.service import get_post


async def create_report(session: AsyncSession, reporter: User, payload: ReportCreateRequest) -> Report:
    if payload.post_id is not None:
        await get_post(session, payload.post_id)
    else:
        await get_comment(session, payload.comment_id)
    target_filter = Report.post_id == payload.post_id if payload.post_id is not None else Report.comment_id == payload.comment_id
    duplicate = await session.scalar(select(Report.id).where(Report.reporter_id == reporter.id, Report.status == "open", target_filter))
    if duplicate is not None:
        raise AppError("RESOURCE_CONFLICT", "An open report already exists for this target", 409)
    report = Report(reporter_id=reporter.id, post_id=payload.post_id, comment_id=payload.comment_id, reason=payload.reason, details=payload.details, created_at=datetime.now(timezone.utc))
    session.add(report)
    await session.flush()
    return report


async def log_action(session: AsyncSession, actor: User, action: str, target_type: str, target_id: UUID, reason: str | None = None) -> None:
    session.add(ModerationAction(actor_id=actor.id, action=action, target_type=target_type, target_id=target_id, reason=reason))


def _scope(status: str) -> str:
    return hashlib.sha256(status.encode()).hexdigest()


def _encode_cursor(report: Report, scope: str, settings: Settings) -> str:
    payload = {"v": 1, "resource": "reports", "created_at": report.created_at.isoformat(), "id": str(report.id), "scope": scope}
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
        if payload["v"] != 1 or payload["resource"] != "reports" or payload["scope"] != scope:
            raise ValueError
        return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None


async def serialize_reports(session: AsyncSession, reports: list[Report]) -> list[ReportRead]:
    if not reports:
        return []
    reporters = {user.id: user for user in (await session.scalars(select(User).where(User.id.in_({report.reporter_id for report in reports})))).all()}
    post_ids = {report.post_id for report in reports if report.post_id is not None}
    comment_ids = {report.comment_id for report in reports if report.comment_id is not None}
    posts = {post.id: post for post in (await session.scalars(select(Post).where(Post.id.in_(post_ids)))).all()} if post_ids else {}
    comments = {comment.id: comment for comment in (await session.scalars(select(Comment).where(Comment.id.in_(comment_ids)))).all()} if comment_ids else {}
    result = []
    for report in reports:
        target = None
        if report.post_id is not None and report.post_id in posts:
            post = posts[report.post_id]
            target = ReportTarget(kind="post", id=post.id, title=post.title, body=post.content, is_deleted=post.deleted_at is not None)
        elif report.comment_id is not None and report.comment_id in comments:
            comment = comments[report.comment_id]
            target = ReportTarget(kind="comment", id=comment.id, body="[deleted]" if comment.deleted_at else comment.body, is_deleted=comment.deleted_at is not None)
        result.append(ReportRead(id=report.id, reporter=user_summary(reporters[report.reporter_id]), post_id=report.post_id, comment_id=report.comment_id, reason=report.reason, details=report.details, status=report.status, resolution=report.resolution, created_at=report.created_at, resolved_at=report.resolved_at, target=target))
    return result


async def get_report(session: AsyncSession, report_id: UUID) -> Report:
    report = await session.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise AppError("RESOURCE_NOT_FOUND", "Report not found", 404)
    return report


async def count_open_reports(session: AsyncSession) -> ReportCount:
    count = await session.scalar(select(func.count()).select_from(Report).where(Report.status == "open"))
    return ReportCount(open_count=count or 0)


async def list_reports(session: AsyncSession, *, settings: Settings, status: str, cursor: str | None, limit: int) -> ReportPage:
    if status not in {"open", "resolved", "rejected"}:
        raise AppError("VALIDATION_ERROR", "Unsupported report status", 422)
    scope = _scope(status)
    query = select(Report).where(Report.status == status)
    sqlite_cursor_id: UUID | None = None
    if cursor:
        created_at, report_id = _decode_cursor(cursor, scope, settings)
        if session.bind and session.bind.dialect.name == "postgresql":
            query = query.where((Report.created_at > created_at) | ((Report.created_at == created_at) & (Report.id > report_id)))
        else:
            sqlite_cursor_id = report_id
    reports = (await session.scalars(query.order_by(Report.created_at, Report.id))).all() if sqlite_cursor_id else (await session.scalars(query.order_by(Report.created_at, Report.id).limit(limit + 1))).all()
    if sqlite_cursor_id:
        try:
            reports = reports[[report.id for report in reports].index(sqlite_cursor_id) + 1 : limit + 2]
        except ValueError:
            raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None
    next_cursor = _encode_cursor(reports[limit - 1], scope, settings) if len(reports) > limit else None
    return ReportPage(items=await serialize_reports(session, reports[:limit]), next_cursor=next_cursor)


async def resolve_report(session: AsyncSession, report_id: UUID, payload: ReportUpdateRequest) -> Report:
    report = await session.scalar(select(Report).where(Report.id == report_id))
    if report is None:
        raise AppError("RESOURCE_NOT_FOUND", "Report not found", 404)
    if report.status != "open":
        raise AppError("RESOURCE_CONFLICT", "Report is already processed", 409)
    report.status = payload.status
    report.resolution = payload.resolution
    report.resolved_at = datetime.now(timezone.utc)
    await session.flush()
    return report


async def list_users(session: AsyncSession, query_text: str | None, limit: int, banned: bool | None = None, muted: bool | None = None) -> list[AdminUserRead]:
    query = select(User)
    if query_text:
        pattern = f"%{query_text.strip().casefold()}%"
        query = query.where(User.username_normalized.ilike(pattern) | User.email_normalized.ilike(pattern))
    if banned is True:
        query = query.where(User.status == "banned")
    elif banned is False:
        query = query.where(User.status != "banned")
    if muted is True:
        query = query.where(User.muted_until.is_not(None), User.muted_until > func.now())
    elif muted is False:
        query = query.where((User.muted_until.is_(None)) | (User.muted_until <= func.now()))
    users = (await session.scalars(query.order_by(User.username_normalized).limit(limit))).all()
    return [AdminUserRead(**user_summary(user).model_dump(), email=user.email, role=user.role, disabled_at=user.disabled_at, muted_until=user.muted_until, moderation_reason=user.moderation_reason) for user in users]


async def moderate_user(session: AsyncSession, actor: User, user_id: UUID, payload: UserModerationRequest) -> User:
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise AppError("RESOURCE_NOT_FOUND", "User not found", 404)
    if user.id == actor.id or user.role == "admin":
        raise AppError("FORBIDDEN", "Administrators cannot moderate this user", 403)
    if actor.role == "moderator" and (payload.action != "ban" or user.role != "user" or not payload.reason):
        raise AppError("FORBIDDEN", "Moderator can only ban users with a reason", 403)
    now = datetime.now(timezone.utc)
    if payload.action == "ban":
        user.disabled_at = now
        user.status = "banned"
        user.muted_until = None
        await session.execute(update(RefreshSession).where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None)).values(revoked_at=now))
    elif payload.action == "unban":
        user.disabled_at = None
        user.status = "active"
    elif payload.action == "mute":
        if payload.muted_until <= now:
            raise AppError("VALIDATION_ERROR", "Mute expiry must be in the future", 422)
        user.muted_until = payload.muted_until
    else:
        user.muted_until = None
    user.moderation_reason = payload.reason
    await log_action(session, actor, f"user_{payload.action}", "user", user.id, payload.reason)
    await session.flush()
    return user


async def delete_user(session: AsyncSession, actor: User, user_id: UUID) -> None:
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise AppError("RESOURCE_NOT_FOUND", "User not found", 404)
    if user.id == actor.id or user.role == "admin":
        raise AppError("FORBIDDEN", "Administrators cannot delete this user", 403)
    now = datetime.now(timezone.utc)
    await session.execute(delete(RefreshSession).where(RefreshSession.user_id == user.id))
    await session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    await session.execute(delete(PostLike).where(PostLike.user_id == user.id))
    await session.execute(delete(PostBookmark).where(PostBookmark.user_id == user.id))
    await session.execute(delete(ShareEvent).where(ShareEvent.user_id == user.id))
    user.username = f"deleted-{str(user.id).replace('-', '')[:20]}"
    user.username_normalized = user.username
    user.email = f"deleted-{user.id}@deleted.invalid"
    user.email_normalized = user.email
    user.password_hash = "deleted"
    user.avatar_media_id = None
    user.cover_media_id = None
    user.display_name = None
    user.bio = None
    user.profile_visibility = "private"
    user.status = "deleted"
    user.disabled_at = now
    user.muted_until = None
    user.moderation_reason = None
    await log_action(session, actor, "user_delete", "user", user.id, "Account deleted")
    await session.flush()


async def change_user_role(session: AsyncSession, actor: User, user_id: UUID, payload: UserRoleRequest) -> User:
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise AppError("RESOURCE_NOT_FOUND", "User not found", 404)
    if user.id == actor.id or user.role == "admin":
        raise AppError("FORBIDDEN", "Administrators cannot change this role", 403)
    old_role = user.role
    user.role = payload.role
    await log_action(session, actor, "user_role", "user", user.id, f"{old_role}->{payload.role}: {payload.reason}")
    await session.flush()
    return user


async def hide_post(session: AsyncSession, actor: User, post_id: UUID, reason: str) -> Post:
    post = await session.scalar(select(Post).where(Post.id == post_id).with_for_update())
    if post is None:
        raise AppError("RESOURCE_NOT_FOUND", "Post not found", 404)
    if post.deleted_at is None:
        post.deleted_at = datetime.now(timezone.utc)
    await log_action(session, actor, "post_hide", "post", post.id, reason)
    await session.flush()
    return post


async def restore_post(session: AsyncSession, actor: User, post_id: UUID, reason: str) -> Post:
    post = await session.scalar(select(Post).where(Post.id == post_id).with_for_update())
    if post is None:
        raise AppError("RESOURCE_NOT_FOUND", "Post not found", 404)
    post.deleted_at = None
    await log_action(session, actor, "post_restore", "post", post.id, reason)
    await session.flush()
    return post


async def hide_comment(session: AsyncSession, actor: User, comment_id: UUID, reason: str) -> Comment:
    comment = await session.scalar(select(Comment).where(Comment.id == comment_id).with_for_update())
    if comment is None:
        raise AppError("RESOURCE_NOT_FOUND", "Comment not found", 404)
    if comment.deleted_at is None:
        comment.deleted_at = datetime.now(timezone.utc)
    await log_action(session, actor, "comment_hide", "comment", comment.id, reason)
    await session.flush()
    return comment


async def restore_comment(session: AsyncSession, actor: User, comment_id: UUID, reason: str) -> Comment:
    comment = await session.scalar(select(Comment).where(Comment.id == comment_id).with_for_update())
    if comment is None:
        raise AppError("RESOURCE_NOT_FOUND", "Comment not found", 404)
    comment.deleted_at = None
    await log_action(session, actor, "comment_restore", "comment", comment.id, reason)
    await session.flush()
    return comment


async def apply_report_actions(session: AsyncSession, actor: User, report: Report, payload: ReportUpdateRequest) -> None:
    if payload.status != "resolved":
        return
    reason = payload.resolution or "Report resolved"
    target_author_id: UUID | None = None
    if report.post_id is not None:
        post = await session.get(Post, report.post_id)
        if post:
            target_author_id = post.author_id
            if payload.hide_target:
                await hide_post(session, actor, post.id, reason)
    elif report.comment_id is not None:
        comment = await session.get(Comment, report.comment_id)
        if comment:
            target_author_id = comment.author_id
            if payload.hide_target:
                await hide_comment(session, actor, comment.id, reason)
    if payload.ban_author and target_author_id is not None:
        await moderate_user(session, actor, target_author_id, UserModerationRequest(action="ban", reason=reason))


def _action_scope(actor_id: UUID | None, action: str | None) -> str:
    return hashlib.sha256(json.dumps({"actor_id": str(actor_id) if actor_id else None, "action": action}, sort_keys=True).encode()).hexdigest()


def _encode_action_cursor(action: ModerationAction, scope: str, settings: Settings) -> str:
    payload = {"v": 1, "resource": "moderation_actions", "created_at": action.created_at.isoformat(), "id": str(action.id), "scope": scope}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_action_cursor(value: str, scope: str, settings: Settings) -> tuple[datetime, UUID]:
    try:
        encoded, signature = value.split(".", 1)
        expected = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["v"] != 1 or payload["resource"] != "moderation_actions" or payload["scope"] != scope:
            raise ValueError
        return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None


async def list_actions(session: AsyncSession, *, settings: Settings, actor_id: UUID | None, action: str | None, cursor: str | None, limit: int) -> ModerationActionPage:
    scope = _action_scope(actor_id, action)
    query = select(ModerationAction)
    if actor_id:
        query = query.where(ModerationAction.actor_id == actor_id)
    if action:
        query = query.where(ModerationAction.action == action)
    if cursor:
        created_at, action_id = _decode_action_cursor(cursor, scope, settings)
        query = query.where((ModerationAction.created_at < created_at) | ((ModerationAction.created_at == created_at) & (ModerationAction.id < action_id)))
    rows = (await session.scalars(query.order_by(ModerationAction.created_at.desc(), ModerationAction.id.desc()).limit(limit + 1))).all()
    actor_ids = {row.actor_id for row in rows[:limit]}
    actors = {user.id: user for user in (await session.scalars(select(User).where(User.id.in_(actor_ids)))).all()} if actor_ids else {}
    items = [ModerationActionRead(id=row.id, actor=user_summary(actors[row.actor_id]), action=row.action, target_type=row.target_type, target_id=row.target_id, reason=row.reason, created_at=row.created_at) for row in rows[:limit]]
    next_cursor = _encode_action_cursor(rows[limit - 1], scope, settings) if len(rows) > limit else None
    return ModerationActionPage(items=items, next_cursor=next_cursor)
