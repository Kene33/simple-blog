from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import AppError
from src.db.models import Media, Post, User
from src.modules.auth.schemas import PublicUserProfile, UserProfile, UserUpdateRequest
from src.modules.auth.service import normalize_email, normalize_username, user_summary


async def profile_for_user(session: AsyncSession, user: User, include_private: bool) -> UserProfile | PublicUserProfile:
    posts_count = await session.scalar(select(func.count()).select_from(Post).where(Post.author_id == user.id, Post.deleted_at.is_(None)))
    values = user_summary(user).model_dump() | {"posts_count": posts_count or 0, "created_at": user.created_at, "updated_at": user.updated_at}
    if include_private:
        return UserProfile(**values, email=user.email, role=user.role)
    return PublicUserProfile(**values)


async def find_public_user(session: AsyncSession, username: str) -> User:
    user = await session.scalar(select(User).where(User.username_normalized == normalize_username(username), User.disabled_at.is_(None)))
    if user is None:
        raise AppError("RESOURCE_NOT_FOUND", "User not found", 404)
    return user


async def update_user(session: AsyncSession, user: User, payload: UserUpdateRequest) -> User:
    if not payload.has_changes():
        raise AppError("VALIDATION_ERROR", "At least one field must be provided", 422)
    values: dict[str, object] = {}
    if "username" in payload.model_fields_set and payload.username is not None:
        values["username"] = payload.username
        values["username_normalized"] = normalize_username(payload.username)
    if "email" in payload.model_fields_set and payload.email is not None:
        values["email"] = str(payload.email)
        values["email_normalized"] = normalize_email(str(payload.email))
    if values:
        duplicate = await session.scalar(select(User.id).where(User.id != user.id, or_(User.username_normalized == values.get("username_normalized", user.username_normalized), User.email_normalized == values.get("email_normalized", user.email_normalized))))
        if duplicate:
            raise AppError("RESOURCE_CONFLICT", "Username or email is already in use", 409)
        for field, value in values.items():
            setattr(user, field, value)
    if "avatar_media_id" in payload.model_fields_set:
        if payload.avatar_media_id is None:
            user.avatar_media_id = None
        else:
            media = await session.scalar(select(Media).where(Media.id == payload.avatar_media_id, Media.owner_id == user.id, Media.kind == "image", Media.deleted_at.is_(None)))
            if media is None:
                raise AppError("VALIDATION_ERROR", "Avatar must be an active image owned by the user", 422)
            user.avatar_media_id = media.id
    await session.flush()
    return user
