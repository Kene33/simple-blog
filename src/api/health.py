from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from src.db.session import engine

router = APIRouter(prefix="/health", tags=["health"])
meta_router = APIRouter(tags=["meta"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=None)
async def ready(request: Request) -> dict[str, object] | JSONResponse:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            await connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "service": request.app.title, "checks": {"database": "unavailable"}})
    return {"status": "ready", "service": request.app.title, "checks": {"database": "ok"}}


@meta_router.get("/robots.txt", include_in_schema=False, response_class=PlainTextResponse)
async def robots() -> str:
    return "User-agent: *\nAllow: /\n"
