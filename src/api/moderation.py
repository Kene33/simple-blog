from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.errors import AppError
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, require_admin, require_csrf, require_staff
from src.modules.moderation.schemas import (
    AdminUserRead,
    ContentModerationRequest,
    ModerationActionPage,
    ReportCount,
    ReportCreateRequest,
    ReportPage,
    ReportRead,
    ReportUpdateRequest,
    UserModerationRequest,
    UserRoleRequest,
)
from src.modules.moderation.service import (
    apply_report_actions,
    change_user_role,
    count_open_reports,
    create_report,
    get_report,
    hide_comment,
    hide_post,
    list_actions,
    list_reports,
    list_users,
    log_action,
    moderate_user,
    resolve_report,
    restore_comment,
    restore_post,
    serialize_reports,
)

router = APIRouter(prefix="/api/v1", tags=["moderation"])


@router.post("/reports", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
async def create(payload: ReportCreateRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> ReportRead:
    try:
        report = await create_report(session, auth.user, payload)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise AppError("RESOURCE_CONFLICT", "An open report already exists for this target", 409) from None
    return (await serialize_reports(session, [report]))[0]


@router.get("/admin/reports", response_model=ReportPage)
async def list_admin(status: str = "open", cursor: str | None = None, limit: int = 20, _: CurrentAuth = Depends(require_staff), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> ReportPage:
    return await list_reports(session, settings=settings, status=status, cursor=cursor, limit=min(max(limit, 1), 100))


@router.get("/admin/reports/count", response_model=ReportCount)
async def count(_: CurrentAuth = Depends(require_staff), session: AsyncSession = Depends(get_session)) -> ReportCount:
    return await count_open_reports(session)


@router.get("/admin/reports/{report_id}", response_model=ReportRead)
async def detail(report_id: UUID, _: CurrentAuth = Depends(require_staff), session: AsyncSession = Depends(get_session)) -> ReportRead:
    return (await serialize_reports(session, [await get_report(session, report_id)]))[0]


@router.patch("/admin/reports/{report_id}", response_model=ReportRead)
async def resolve(report_id: UUID, payload: ReportUpdateRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> ReportRead:
    if auth.user.role not in {"admin", "moderator"}:
        raise AppError("FORBIDDEN", "Moderator role is required", 403)
    if auth.user.role == "moderator" and not payload.resolution:
        raise AppError("VALIDATION_ERROR", "Resolution is required", 422)
    report = await resolve_report(session, report_id, payload)
    await apply_report_actions(session, auth.user, report, payload)
    await log_action(session, auth.user, f"report_{payload.status}", "report", report.id, payload.resolution)
    await session.commit()
    await session.refresh(report)
    return (await serialize_reports(session, [report]))[0]


@router.get("/admin/users", response_model=list[AdminUserRead])
async def users(query: str | None = None, limit: int = 20, _: CurrentAuth = Depends(require_staff), session: AsyncSession = Depends(get_session)) -> list[AdminUserRead]:
    return await list_users(session, query, min(max(limit, 1), 100))


@router.patch("/admin/users/{user_id}/moderation", response_model=AdminUserRead)
async def moderate(user_id: UUID, payload: UserModerationRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> AdminUserRead:
    if auth.user.role not in {"admin", "moderator"}:
        raise AppError("FORBIDDEN", "Moderator role is required", 403)
    user = await moderate_user(session, auth.user, user_id, payload)
    await session.commit()
    return AdminUserRead(id=user.id, username=user.username, avatar_url=f"/api/v1/media/{user.avatar_media_id}" if user.avatar_media_id else None, email=user.email, role=user.role, disabled_at=user.disabled_at, muted_until=user.muted_until, moderation_reason=user.moderation_reason)


@router.patch("/admin/users/{user_id}/role", response_model=AdminUserRead)
async def role(user_id: UUID, payload: UserRoleRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> AdminUserRead:
    if auth.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    user = await change_user_role(session, auth.user, user_id, payload)
    await session.commit()
    return AdminUserRead(id=user.id, username=user.username, avatar_url=f"/api/v1/media/{user.avatar_media_id}" if user.avatar_media_id else None, email=user.email, role=user.role, disabled_at=user.disabled_at, muted_until=user.muted_until, moderation_reason=user.moderation_reason)


@router.patch("/admin/posts/{post_id}/hide", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def hide_admin_post(post_id: UUID, payload: ContentModerationRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    if auth.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    await hide_post(session, auth.user, post_id, payload.reason)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/admin/posts/{post_id}/restore", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def restore_admin_post(post_id: UUID, payload: ContentModerationRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    if auth.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    await restore_post(session, auth.user, post_id, payload.reason)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/admin/comments/{comment_id}/hide", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def hide_admin_comment(comment_id: UUID, payload: ContentModerationRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    if auth.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    await hide_comment(session, auth.user, comment_id, payload.reason)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/admin/comments/{comment_id}/restore", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def restore_admin_comment(comment_id: UUID, payload: ContentModerationRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    if auth.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    await restore_comment(session, auth.user, comment_id, payload.reason)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/admin/moderation-actions", response_model=ModerationActionPage)
async def actions(actor_id: UUID | None = None, action: str | None = None, cursor: str | None = None, limit: int = 20, _: CurrentAuth = Depends(require_admin), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> ModerationActionPage:
    return await list_actions(session, settings=settings, actor_id=actor_id, action=action, cursor=cursor, limit=min(max(limit, 1), 100))
