from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.db.session import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live(request: Request) -> dict[str, str]:
    return {"status": "ok", "service": request.app.title, "version": request.app.version}


@router.get("/ready", response_model=None)
async def ready(request: Request) -> dict[str, object] | JSONResponse:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "service": request.app.title, "checks": {"database": "unavailable"}})
    return {"status": "ready", "service": request.app.title, "checks": {"database": "ok"}}
