from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.lifespan import lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    return FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )


app = create_app()
