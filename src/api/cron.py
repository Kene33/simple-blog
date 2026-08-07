import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.db.session import get_session

router = APIRouter(prefix="/api/internal", tags=["internal"])


@router.get("/keepalive", include_in_schema=False, response_model=None)
async def keepalive(request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> dict[str, str] | JSONResponse:
    authorization = request.headers.get("authorization", "")
    if not settings.cron_secret or not secrets.compare_digest(authorization, f"Bearer {settings.cron_secret}"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    for _ in range(5):
        await session.execute(text("SELECT 1"))
    return {"status": "ok"}
