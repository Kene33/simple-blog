from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.cron import router as cron_router
from src.api.health import meta_router
from src.api.health import router as health_router
from src.api.v1 import router as v1_router
from src.core.config import Settings, get_settings
from src.core.errors import (
    AppError,
    app_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from src.core.lifespan import lifespan
from src.core.logging import configure_logging
from src.core.middleware import ObservabilityMiddleware, RequestIdMiddleware, SecurityHeadersMiddleware
from src.core.rate_limit import RateLimiter
from src.core.realtime import RealtimeHub


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.state.rate_limiter = RateLimiter(resolved_settings.redis_url)
    application.state.realtime_hub = RealtimeHub()
    application.state.settings = resolved_settings
    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(ObservabilityMiddleware)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(GZipMiddleware, minimum_size=1000)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", resolved_settings.csrf_header_name, "X-Request-ID"],
    )
    application.add_exception_handler(AppError, app_error_handler)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)
    application.include_router(health_router)
    application.include_router(cron_router)
    application.include_router(meta_router)
    application.include_router(v1_router)
    return application


app = create_app()
