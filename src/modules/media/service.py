from datetime import datetime, timezone
from uuid import UUID

import filetype
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import AppError
from src.db.models import Media
from src.modules.media.schemas import MediaPurpose, MediaRead
from src.modules.media.storage import S3Storage

MIME_TYPES = {"image/jpeg": "image", "image/png": "image", "image/gif": "image", "image/webp": "image", "video/mp4": "video", "video/webm": "video"}


def as_read(media: Media) -> MediaRead:
    return MediaRead(id=media.id, kind=media.kind, purpose=media.purpose, mime_type=media.mime_type, size_bytes=media.size_bytes, url=f"/api/v1/media/{media.id}", status=media.status, created_at=media.created_at)


async def upload_media(session: AsyncSession, storage: S3Storage, owner_id: UUID, purpose: MediaPurpose, content: bytes) -> Media:
    detected = filetype.guess_mime(content)
    kind = MIME_TYPES.get(detected or "")
    if kind is None:
        raise AppError("MEDIA_UNSUPPORTED", "Unsupported media type", 415)
    limit = 5 * 1024 * 1024 if purpose == "avatar" else (10 * 1024 * 1024 if kind == "image" else 100 * 1024 * 1024)
    if purpose == "avatar" and kind != "image":
        raise AppError("MEDIA_UNSUPPORTED", "Unsupported media purpose", 415)
    if len(content) > limit:
        raise AppError("MEDIA_TOO_LARGE", "Media exceeds its size limit", 413)
    key = storage.key_for(owner_id, detected)
    await storage.put(key, content, detected)
    media = Media(owner_id=owner_id, purpose=purpose, kind=kind, mime_type=detected, size_bytes=len(content), storage_key=key, status="uploaded")
    session.add(media)
    try:
        await session.flush()
    except Exception:
        await storage.delete(key)
        raise
    return media


async def owned_media(session: AsyncSession, media_id: UUID, owner_id: UUID) -> Media:
    media = await session.scalar(select(Media).where(Media.id == media_id, Media.owner_id == owner_id, Media.deleted_at.is_(None)))
    if media is None:
        raise AppError("RESOURCE_NOT_FOUND", "Media not found", 404)
    return media


async def delete_media(session: AsyncSession, storage: S3Storage, media: Media) -> None:
    if media.status == "attached":
        raise AppError("RESOURCE_CONFLICT", "Attached media cannot be deleted", 409)
    await storage.delete(media.storage_key)
    media.status = "deleted"
    media.deleted_at = datetime.now(timezone.utc)


async def cleanup_orphan_media(session: AsyncSession, storage: S3Storage, older_than: datetime) -> int:
    candidates = (await session.scalars(select(Media).where(Media.status == "uploaded", Media.created_at < older_than, Media.deleted_at.is_(None)))).all()
    for media in candidates:
        await storage.delete(media.storage_key)
        media.status = "deleted"
        media.deleted_at = datetime.now(timezone.utc)
    await session.flush()
    return len(candidates)
