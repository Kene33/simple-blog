import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

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
    if refresh_session is None or refresh_session.revoked_at is not None or refresh_session.expires_at <= datetime.now(timezone.utc):
        raise AppError("AUTH_INVALID", "Authentication is required", 401)
    return CurrentAuth(user=user, session_id=session_id, csrf_token=csrf_token)


async def require_csrf(request: Request, auth: CurrentAuth = Depends(get_current_auth), settings: Settings = Depends(get_settings)) -> CurrentAuth:
    header_token = request.headers.get(settings.csrf_header_name)
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not header_token or not cookie_token or not secrets.compare_digest(header_token, cookie_token) or not secrets.compare_digest(header_token, auth.csrf_token):
        raise AppError("CSRF_FAILED", "CSRF validation failed", 403)
    return auth


async def require_admin(auth: CurrentAuth = Depends(get_current_auth)) -> CurrentAuth:
    if auth.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    return auth


def validate_refresh_csrf(request: Request, settings: Settings) -> str:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    header_token = request.headers.get(settings.csrf_header_name)
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not refresh_token or not header_token or not cookie_token:
        raise AppError("CSRF_FAILED", "CSRF validation failed", 403)
    try:
        payload = decode_token(settings, refresh_token, "refresh")
        token_csrf = payload["csrf"]
    except (KeyError, ValueError):
        raise AppError("AUTH_INVALID", "Invalid refresh token", 401) from None
    if not secrets.compare_digest(header_token, cookie_token) or not secrets.compare_digest(header_token, token_csrf):
        raise AppError("CSRF_FAILED", "CSRF validation failed", 403)
    return refresh_token
