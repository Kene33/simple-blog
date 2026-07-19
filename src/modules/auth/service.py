import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.core.security import TokenData, create_access_token, create_refresh_token, hash_password, token_hash, verify_password
from src.db.models import RefreshSession, User
from src.modules.auth.schemas import LoginRequest, RegisterRequest, SessionRead, UserSummary


@dataclass(frozen=True)
class AuthSession:
    access: TokenData
    refresh: TokenData
    csrf_token: str
    response: SessionRead


def normalize_username(value: str) -> str:
    return value.strip().casefold()


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def user_summary(user: User) -> UserSummary:
    return UserSummary(id=user.id, username=user.username, avatar_url=f"/api/v1/media/{user.avatar_media_id}" if user.avatar_media_id else None)


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
    if user is None or user.disabled_at is not None or not verify_password(payload.password, user.password_hash):
        raise AppError("AUTH_INVALID", "Invalid credentials", 401)
    return user


async def create_session(session: AsyncSession, settings: Settings, user: User, csrf_token: str) -> AuthSession:
    session_id = uuid.uuid4()
    access = create_access_token(settings, user.id, session_id, csrf_token)
    refresh = create_refresh_token(settings, user.id, session_id, csrf_token)
    session.add(RefreshSession(id=session_id, user_id=user.id, token_hash=token_hash(refresh.value), expires_at=refresh.expires_at))
    await session.flush()
    return AuthSession(access=access, refresh=refresh, csrf_token=csrf_token, response=SessionRead(user=user_summary(user), access_expires_at=access.expires_at, refresh_expires_at=refresh.expires_at))


async def rotate_session(session: AsyncSession, settings: Settings, refresh_value: str, csrf_token: str) -> AuthSession:
    from src.core.security import decode_token

    try:
        payload = decode_token(settings, refresh_value, "refresh")
        session_id = uuid.UUID(payload["sid"])
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise AppError("AUTH_INVALID", "Invalid refresh token", 401) from None
    refresh_session = await session.scalar(select(RefreshSession).where(RefreshSession.id == session_id, RefreshSession.user_id == user_id).with_for_update())
    now = datetime.now(timezone.utc)
    if refresh_session is None or refresh_session.expires_at <= now or refresh_session.token_hash != token_hash(refresh_value):
        raise AppError("AUTH_INVALID", "Invalid refresh token", 401)
    if refresh_session.revoked_at is not None:
        await session.execute(update(RefreshSession).where(RefreshSession.user_id == user_id, RefreshSession.revoked_at.is_(None)).values(revoked_at=now))
        await session.commit()
        raise AppError("AUTH_INVALID", "Invalid refresh token", 401)
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
