from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.errors import AppError
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, require_admin, require_csrf
from src.modules.moderation.schemas import ReportCreateRequest, ReportPage, ReportRead, ReportUpdateRequest
from src.modules.moderation.service import create_report, list_reports, resolve_report, serialize_reports

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


@router.patch("/admin/reports/{report_id}", response_model=ReportRead)
async def resolve(report_id: UUID, payload: ReportUpdateRequest, _: CurrentAuth = Depends(require_admin), session: AsyncSession = Depends(get_session)) -> ReportRead:
    report = await resolve_report(session, report_id, payload)
    await session.commit()
    await session.refresh(report)
    return (await serialize_reports(session, [report]))[0]
