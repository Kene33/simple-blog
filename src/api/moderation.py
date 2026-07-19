from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import AppError
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, require_csrf
from src.modules.moderation.schemas import ReportCreateRequest
from src.modules.moderation.service import create_report

router = APIRouter(prefix="/api/v1", tags=["moderation"])


@router.post("/reports", status_code=status.HTTP_201_CREATED)
async def create(payload: ReportCreateRequest, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    try:
        report = await create_report(session, auth.user, payload)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise AppError("RESOURCE_CONFLICT", "An open report already exists for this target", 409) from None
    return {"id": str(report.id), "status": report.status}
