from datetime import datetime, timezone
from io import BytesIO
from typing import BinaryIO
from uuid import UUID

from PIL import Image, ImageOps
from PIL.Image import DecompressionBombError, UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.db.models import Media, PostMedia, User
from src.modules.media.schemas import MediaPurpose, MediaRead
from src.modules.media.storage import S3Storage

MIME_TYPES = {"image/jpeg": "image", "image/png": "image", "image/gif": "image", "image/webp": "image", "video/mp4": "video", "video/webm": "video"}


def as_read(media: Media) -> MediaRead:
    return MediaRead(id=media.id, kind=media.kind, purpose=media.purpose, mime_type=media.mime_type, size_bytes=media.size_bytes, url=f"/api/v1/media/{media.id}", status=media.status, created_at=media.created_at)


async def upload_media(session: AsyncSession, storage: S3Storage, owner_id: UUID, purpose: MediaPurpose, stream: BinaryIO, mime_type: str | None, size_bytes: int, settings: Settings) -> Media:
    kind = MIME_TYPES.get(mime_type or "")
    if kind is None:
        raise AppError("MEDIA_UNSUPPORTED", "Unsupported media type", 415)
    limit = 5 * 1024 * 1024 if purpose == "avatar" else (10 * 1024 * 1024 if kind == "image" else 100 * 1024 * 1024)
    if purpose in {"avatar", "cover"} and kind != "image":
        raise AppError("MEDIA_UNSUPPORTED", "Unsupported media purpose", 415)
    if kind == "image":
        stream, mime_type, size_bytes = optimize_image(stream, purpose)
    if size_bytes > limit:
        raise AppError("MEDIA_TOO_LARGE", "Media exceeds its size limit", 413)
    owner = await session.scalar(select(User).where(User.id == owner_id).with_for_update())
    if owner is None:
        raise AppError("AUTH_INVALID", "User not found", 401)
    usage, files, pending = (await session.execute(select(func.coalesce(func.sum(Media.size_bytes), 0), func.count(Media.id), func.count(Media.id).filter(Media.status == "pending")).where(Media.owner_id == owner_id, Media.deleted_at.is_(None)))).one()
    if usage + size_bytes > settings.media_quota_bytes or files >= settings.media_quota_files or pending >= settings.media_pending_limit:
        raise AppError("MEDIA_QUOTA_EXCEEDED", "Media quota exceeded", 413)
    key = storage.key_for(owner_id, mime_type)
    await storage.put_file(key, stream, mime_type)
    media = Media(owner_id=owner_id, purpose=purpose, kind=kind, mime_type=mime_type, size_bytes=size_bytes, storage_key=key, status="uploaded")
    session.add(media)
    try:
        await session.flush()
    except Exception:
        await storage.delete(key)
        raise
    return media


def optimize_image(stream: BinaryIO, purpose: MediaPurpose) -> tuple[BytesIO, str, int]:
    Image.MAX_IMAGE_PIXELS = 20_000_000
    stream.seek(0)
    try:
        with Image.open(stream) as source:
            source.load()
            image = ImageOps.exif_transpose(source)
            image.thumbnail((1024, 1024) if purpose == "avatar" else (2400, 2400), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            output = BytesIO()
            image.save(output, format="WEBP", quality=82, method=4)
    except (DecompressionBombError, UnidentifiedImageError, OSError) as error:
        raise AppError("MEDIA_INVALID", "Image content is invalid", 415) from error
    output.seek(0)
    return output, "image/webp", output.getbuffer().nbytes


async def owned_media(session: AsyncSession, media_id: UUID, owner_id: UUID) -> Media:
    media = await session.scalar(select(Media).where(Media.id == media_id, Media.owner_id == owner_id, Media.deleted_at.is_(None)))
    if media is None:
        raise AppError("RESOURCE_NOT_FOUND", "Media not found", 404)
    return media


async def replace_post_media(session: AsyncSession, post_id: UUID, owner_id: UUID, media_ids: list[UUID]) -> None:
    media = []
    if media_ids:
        media = (await session.scalars(select(Media).where(Media.id.in_(media_ids), Media.owner_id == owner_id, Media.purpose == "post", Media.status == "uploaded", Media.deleted_at.is_(None)))).all()
        if len(media) != len(media_ids) or sum(item.kind == "video" for item in media) > 1:
            raise AppError("VALIDATION_ERROR", "Media must be active post uploads owned by the author and include at most one video", 422)
    previous_media = (await session.scalars(select(Media).join(PostMedia, PostMedia.media_id == Media.id).where(PostMedia.post_id == post_id))).all()
    await session.execute(PostMedia.__table__.delete().where(PostMedia.post_id == post_id))
    for item in previous_media:
        item.status = "uploaded"
        item.attached_at = None
    now = datetime.now(timezone.utc)
    for position, media_id in enumerate(media_ids):
        session.add(PostMedia(post_id=post_id, media_id=media_id, position=position))
    for item in media:
        item.status = "attached"
        item.attached_at = now


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
