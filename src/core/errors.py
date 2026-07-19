import logging
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, fields: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.fields = fields or []


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "-")


def _response(request: Request, status_code: int, code: str, message: str, fields: list[dict[str, Any]] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": _request_id(request),
                "fields": fields or [],
            }
        },
        headers={"X-Request-ID": _request_id(request)},
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _response(request, exc.status_code, exc.code, exc.message, exc.fields)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = f"HTTP_{exc.status_code}"
    message = str(exc.detail)
    if isinstance(exc.detail, Mapping):
        code = str(exc.detail.get("code", code))
        message = str(exc.detail.get("message", message))
    return _response(request, exc.status_code, code, message)


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = [{"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]} for error in exc.errors()]
    return _response(request, 422, "VALIDATION_ERROR", "Request validation failed", fields)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application exception")
    return _response(request, 500, "INTERNAL_ERROR", "Internal server error")
