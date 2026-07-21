import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.core.security import TokenData, create_access_token, create_refresh_token, hash_password, token_hash, verify_password
from src.db.models import PasswordResetToken, RefreshSession, User
from src.modules.auth.schemas import LoginRequest, PasswordResetConfirmRequest, RegisterRequest, SessionRead, UserSummary


@dataclass(frozen=True)
class AuthSession:
    access: TokenData
    refresh: TokenData
    csrf_token: str
    response: SessionRead


class RefreshReplayDetected(AppError):
    pass


DUMMY_PASSWORD_HASH = hash_password("not-a-real-password")


def _is_expired(value: datetime) -> bool:
    return value.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc) if value.tzinfo is None else value <= datetime.now(timezone.utc)


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def user_summary(user: User) -> UserSummary:
    deleted = user.status == "deleted"
    return UserSummary(id=user.id, username="Deleted user" if deleted else user.username, avatar_url=None if deleted else (f"/api/v1/media/{user.avatar_media_id}" if user.avatar_media_id else None), status=user.status, is_banned=user.status == "banned", is_deleted=deleted)


async def register_user(session: AsyncSession, payload: RegisterRequest) -> User:
    username_normalized = normalize_username(payload.username)
    email_normalized = normalize_email(str(payload.email))
    existing = await session.scalar(select(User.id).where(or_(User.username_normalized == username_normalized, User.email_normalized == email_normalized)))
    if existing:
        raise AppError("RESOURCE_CONFLICT", "Username or email is already in use", 409)
    user = User(username=payload.username, username_normalized=username_normalized, email=str(payload.email), email_normalized=email_normalized, password_hash=hash_password(payload.password))
    session.add(user)
    await session.flush()
    return user


async def authenticate_user(session: AsyncSession, payload: LoginRequest) -> User:
    identifier = normalize_email(payload.identifier)
    user = await session.scalar(select(User).where(or_(User.username_normalized == identifier, User.email_normalized == identifier)))
    password_valid = verify_password(payload.password, user.password_hash if user and user.disabled_at is None else DUMMY_PASSWORD_HASH)
    if user is None or user.disabled_at is not None or not password_valid:
        raise AppError("AUTH_INVALID", "Invalid credentials", 401)
    return user


async def create_session(session: AsyncSession, settings: Settings, user: User, csrf_token: str) -> AuthSession:
    session_id = uuid.uuid4()
    access = create_access_token(settings, user.id, session_id, csrf_token)
    refresh = create_refresh_token(settings, user.id, session_id, csrf_token)
    session.add(RefreshSession(id=session_id, user_id=user.id, token_hash=token_hash(refresh.value), expires_at=refresh.expires_at))
    await session.flush()
    return AuthSession(access=access, refresh=refresh, csrf_token=csrf_token, response=SessionRead(user=user_summary(user), access_expires_at=access.expires_at, refresh_expires_at=refresh.expires_at))


async def rotate_session(session: AsyncSession, settings: Settings, refresh_value: str, csrf_header: str | None, csrf_cookie: str | None, csrf_token: str) -> AuthSession:
    from src.core.security import decode_token

    try:
        payload = decode_token(settings, refresh_value, "refresh")
        session_id = uuid.UUID(payload["sid"])
        user_id = uuid.UUID(payload["sub"])
        token_csrf = payload["csrf"]
    except (KeyError, ValueError):
        raise AppError("AUTH_INVALID", "Invalid refresh token", 401) from None
    refresh_session = await session.scalar(select(RefreshSession).where(RefreshSession.id == session_id, RefreshSession.user_id == user_id).with_for_update())
    now = datetime.now(timezone.utc)
    if refresh_session is None or _is_expired(refresh_session.expires_at) or refresh_session.token_hash != token_hash(refresh_value):
        raise AppError("AUTH_INVALID", "Invalid refresh token", 401)
    if refresh_session.revoked_at is not None:
        await session.execute(update(RefreshSession).where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None)).values(revoked_at=now))
        raise RefreshReplayDetected("AUTH_INVALID", "Invalid refresh token", 401)
    if not csrf_header or not csrf_cookie or not secrets.compare_digest(csrf_header, csrf_cookie) or not secrets.compare_digest(csrf_header, token_csrf):
        raise AppError("CSRF_FAILED", "CSRF validation failed", 403)
    user = await session.get(User, user_id)
    if user is None or user.disabled_at is not None:
        raise AppError("AUTH_INVALID", "Invalid refresh token", 401)
    refresh_session.revoked_at = now
    refresh_session.last_used_at = now
    return await create_session(session, settings, user, csrf_token)


async def revoke_session(session: AsyncSession, session_id: uuid.UUID, user_id: uuid.UUID) -> None:
    refresh_session = await session.scalar(select(RefreshSession).where(RefreshSession.id == session_id, RefreshSession.user_id == user_id))
    if refresh_session and refresh_session.revoked_at is None:
        refresh_session.revoked_at = datetime.now(timezone.utc)


async def create_password_reset(session: AsyncSession, settings: Settings, email: str) -> str | None:
    user = await session.scalar(select(User).where(User.email_normalized == normalize_email(email)))
    if user is None or user.disabled_at is not None:
        return None
    now = datetime.now(timezone.utc)
    await session.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=now))
    token = secrets.token_urlsafe(32)
    session.add(PasswordResetToken(user_id=user.id, token_hash=token_hash(token), expires_at=now + timedelta(minutes=settings.password_reset_minutes)))
    await session.flush()
    return token


async def reset_password(session: AsyncSession, payload: PasswordResetConfirmRequest) -> None:
    now = datetime.now(timezone.utc)
    reset = await session.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash(payload.token)).with_for_update())
    if reset is None or reset.used_at is not None or _is_expired(reset.expires_at):
        raise AppError("AUTH_INVALID", "Password reset token is invalid or expired", 401)
    user = await session.get(User, reset.user_id)
    if user is None or user.disabled_at is not None:
        raise AppError("AUTH_INVALID", "Password reset token is invalid or expired", 401)
    user.password_hash = hash_password(payload.password)
    reset.used_at = now
    await session.execute(update(RefreshSession).where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None)).values(revoked_at=now))
