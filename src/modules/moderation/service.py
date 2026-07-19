import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.db.models import Comment, Post, Report, User
from src.modules.auth.service import user_summary
from src.modules.comments.service import get_comment
from src.modules.moderation.schemas import ReportCount, ReportCreateRequest, ReportPage, ReportRead, ReportTarget, ReportUpdateRequest
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
