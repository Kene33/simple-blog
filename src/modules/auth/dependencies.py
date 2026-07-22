import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.errors import AppError
from src.core.security import decode_token
from src.db.models import RefreshSession, User
from src.db.session import get_session


@dataclass(frozen=True)
class CurrentAuth:
    user: User
    session_id: uuid.UUID
    csrf_token: str


def _is_expired(value: datetime) -> bool:
    return value.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc) if value.tzinfo is None else value <= datetime.now(timezone.utc)


def _validate_request_origin(request: Request, settings: Settings) -> None:
    if settings.environment != "production":
        return
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origin_list:
        return
    referer = request.headers.get("referer")
    if referer:
        parsed = urlparse(referer)
        referer_origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
        if referer_origin in settings.cors_origin_list:
            return
    raise AppError("CSRF_FAILED", "Request origin is not allowed", 403)


async def get_current_auth(request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> CurrentAuth:
    token = request.cookies.get(settings.access_cookie_name)
    if not token:
        raise AppError("AUTH_REQUIRED", "Authentication is required", 401)
    try:
        payload = decode_token(settings, token, "access")
        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["sid"])
        csrf_token = payload["csrf"]
    except (KeyError, ValueError):
        raise AppError("AUTH_INVALID", "Authentication is required", 401) from None
    user = await session.get(User, user_id)
    if user is None or user.disabled_at is not None:
        raise AppError("AUTH_INVALID", "Authentication is required", 401)
    refresh_session = await session.scalar(select(RefreshSession).where(RefreshSession.id == session_id, RefreshSession.user_id == user_id))
    if refresh_session is None or refresh_session.revoked_at is not None or _is_expired(refresh_session.expires_at):
        raise AppError("AUTH_INVALID", "Authentication is required", 401)
    return CurrentAuth(user=user, session_id=session_id, csrf_token=csrf_token)


async def get_optional_auth(request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> CurrentAuth | None:
    if not request.cookies.get(settings.access_cookie_name):
        return None
    try:
        return await get_current_auth(request, session, settings)
    except AppError as error:
        if error.status_code == 401:
            return None
        raise


async def require_csrf(request: Request, auth: CurrentAuth = Depends(get_current_auth), settings: Settings = Depends(get_settings)) -> CurrentAuth:
    _validate_request_origin(request, settings)
    header_token = request.headers.get(settings.csrf_header_name)
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not header_token or not cookie_token or not secrets.compare_digest(header_token, cookie_token) or not secrets.compare_digest(header_token, auth.csrf_token):
        raise AppError("CSRF_FAILED", "CSRF validation failed", 403)
    return auth


async def require_unmuted_csrf(auth: CurrentAuth = Depends(require_csrf)) -> CurrentAuth:
    muted_until = auth.user.muted_until
    if muted_until is not None and (muted_until.replace(tzinfo=timezone.utc) if muted_until.tzinfo is None else muted_until) > datetime.now(timezone.utc):
        raise AppError("USER_MUTED", "User is muted", 403)
    return auth


async def optional_csrf(request: Request, auth: CurrentAuth | None = Depends(get_optional_auth), settings: Settings = Depends(get_settings)) -> CurrentAuth | None:
    if auth is None:
        return None
    _validate_request_origin(request, settings)
    header_token = request.headers.get(settings.csrf_header_name)
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not header_token or not cookie_token or not secrets.compare_digest(header_token, cookie_token) or not secrets.compare_digest(header_token, auth.csrf_token):
        raise AppError("CSRF_FAILED", "CSRF validation failed", 403)
    return auth


async def require_admin(auth: CurrentAuth = Depends(get_current_auth)) -> CurrentAuth:
    if auth.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    return auth


async def require_staff(auth: CurrentAuth = Depends(get_current_auth)) -> CurrentAuth:
    if auth.user.role not in {"admin", "moderator"}:
        raise AppError("FORBIDDEN", "Moderator role is required", 403)
    return auth
