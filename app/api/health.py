from fastapi import APIRouter, Request

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live(request: Request) -> dict[str, str]:
    return {"status": "ok", "service": request.app.title, "version": request.app.version}


@router.get("/ready")
async def ready(request: Request) -> dict[str, object]:
    return {"status": "ready", "service": request.app.title, "checks": {"application": "ok"}}
