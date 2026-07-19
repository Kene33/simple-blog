from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.core.lifespan import lifespan
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.add_middleware(RequestIdMiddleware)
    return application


app = create_app()
