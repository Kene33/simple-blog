from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import AppError
from src.core.security import hash_password, verify_password
from src.db.models import Media, Post, User
from src.modules.auth.schemas import PublicUserProfile, UserProfile, UserUpdateRequest
from src.modules.auth.service import normalize_email, normalize_username, user_summary


async def profile_for_user(session: AsyncSession, user: User, include_private: bool) -> UserProfile | PublicUserProfile:
    post_filter = [Post.author_id == user.id, Post.status == "published", Post.deleted_at.is_(None)]
    posts_count = 0 if not include_private and user.posts_visibility != "public" else await session.scalar(select(func.count()).select_from(Post).where(*post_filter))
    values = user_summary(user).model_dump() | {"display_name": user.display_name, "bio": user.bio, "cover_url": f"/api/v1/media/{user.cover_media_id}" if user.cover_media_id else None, "posts_count": posts_count or 0, "created_at": user.created_at, "updated_at": user.updated_at}
    if include_private:
        return UserProfile(**values, email=user.email, role=user.role, profile_visibility=user.profile_visibility, posts_visibility=user.posts_visibility, comments_visibility=user.comments_visibility)
    return PublicUserProfile(**values)


async def find_public_user(session: AsyncSession, username: str) -> User:
    user = await session.scalar(select(User).where(User.username_normalized == normalize_username(username), User.profile_visibility == "public", User.disabled_at.is_(None)))
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
        previous_media = await session.get(Media, user.avatar_media_id) if user.avatar_media_id else None
        if payload.avatar_media_id is None:
            user.avatar_media_id = None
        else:
            media = await session.scalar(select(Media).where(Media.id == payload.avatar_media_id, Media.owner_id == user.id, Media.purpose == "avatar", Media.kind == "image", Media.status == "uploaded", Media.deleted_at.is_(None)))
            if media is None:
                raise AppError("VALIDATION_ERROR", "Avatar must be an active image owned by the user", 422)
            user.avatar_media_id = media.id
            media.status = "attached"
            media.attached_at = datetime.now(timezone.utc)
        if previous_media is not None and previous_media.id != user.avatar_media_id:
            previous_media.status = "uploaded"
            previous_media.attached_at = None
    if "cover_media_id" in payload.model_fields_set:
        previous_media = await session.get(Media, user.cover_media_id) if user.cover_media_id else None
        if payload.cover_media_id is None:
            user.cover_media_id = None
        else:
            media = await session.scalar(select(Media).where(Media.id == payload.cover_media_id, Media.owner_id == user.id, Media.purpose == "cover", Media.kind == "image", Media.status == "uploaded", Media.deleted_at.is_(None)))
            if media is None:
                raise AppError("VALIDATION_ERROR", "Cover must be an active image owned by the user", 422)
            user.cover_media_id = media.id
            media.status = "attached"
            media.attached_at = datetime.now(timezone.utc)
        if previous_media is not None and previous_media.id != user.cover_media_id:
            previous_media.status = "uploaded"
            previous_media.attached_at = None
    if "display_name" in payload.model_fields_set:
        user.display_name = payload.display_name
    if "bio" in payload.model_fields_set:
        user.bio = payload.bio
    for field in ("profile_visibility", "posts_visibility", "comments_visibility"):
        if field in payload.model_fields_set:
            setattr(user, field, getattr(payload, field))
    if "new_password" in payload.model_fields_set:
        if not payload.current_password or not payload.new_password:
            raise AppError("VALIDATION_ERROR", "Current and new password are required", 422)
        if not verify_password(payload.current_password, user.password_hash):
            raise AppError("AUTH_INVALID", "Current password is invalid", 401)
        user.password_hash = hash_password(payload.new_password)
    await session.flush()
    return user
