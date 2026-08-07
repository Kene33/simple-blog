import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.db.session import get_session
from src.modules.messaging.service import purge_deleted_messages

router = APIRouter(prefix="/api/internal", tags=["internal"])


def _authorized(request: Request, settings: Settings) -> bool:
    authorization = request.headers.get("authorization", "")
    return bool(settings.cron_secret and secrets.compare_digest(authorization, f"Bearer {settings.cron_secret}"))


@router.get("/keepalive", include_in_schema=False, response_model=None)
async def keepalive(request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> dict[str, str] | JSONResponse:
    if not _authorized(request, settings):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    for _ in range(5):
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.post("/message-retention", include_in_schema=False, response_model=None)
async def message_retention(request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> dict[str, int] | JSONResponse:
    if not _authorized(request, settings):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.message_retention_days)
    deleted = await purge_deleted_messages(session, cutoff)
    await session.commit()
    return {"deleted": deleted}
