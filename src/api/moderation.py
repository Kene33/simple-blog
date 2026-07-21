from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.errors import AppError
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, require_admin, require_csrf
from src.modules.moderation.schemas import AdminUserRead, ReportCount, ReportCreateRequest, ReportPage, ReportRead, ReportUpdateRequest, UserModerationRequest
from src.modules.moderation.service import count_open_reports, create_report, get_report, list_reports, list_users, moderate_user, resolve_report, serialize_reports

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
async def list_admin(status: str = "open", cursor: str | None = None, limit: int = 20, _: CurrentAuth = Depends(require_admin), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> ReportPage:
    return await list_reports(session, settings=settings, status=status, cursor=cursor, limit=min(max(limit, 1), 100))


@router.get("/admin/reports/count", response_model=ReportCount)
async def count(_: CurrentAuth = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> ReportCount:
    return await count_open_reports(session)


@router.get("/admin/reports/{report_id}", response_model=ReportRead)
async def detail(report_id: UUID, _: CurrentAuth = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> ReportRead:
    return (await serialize_reports(session, [await get_report(session, report_id)]))[0]


@router.patch("/admin/reports/{report_id}", response_model=ReportRead)
async def resolve(report_id: UUID, payload: ReportUpdateRequest, _: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> ReportRead:
    if _.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    report = await resolve_report(session, report_id, payload)
    await session.commit()
    await session.refresh(report)
    return (await serialize_reports(session, [report]))[0]


@router.get("/admin/users", response_model=list[AdminUserRead])
async def users(query: str | None = None, limit: int = 20, _: CurrentAuth = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> list[AdminUserRead]:
    return await list_users(session, query, min(max(limit, 1), 100))


@router.patch("/admin/users/{user_id}/moderation", response_model=AdminUserRead)
async def moderate(user_id: UUID, payload: UserModerationRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> AdminUserRead:
    if auth.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    user = await moderate_user(session, auth.user, user_id, payload)
    await session.commit()
    return AdminUserRead(id=user.id, username=user.username, avatar_url=f"/api/v1/media/{user.avatar_media_id}" if user.avatar_media_id else None, email=user.email, role=user.role, disabled_at=user.disabled_at, muted_until=user.muted_until, moderation_reason=user.moderation_reason)
