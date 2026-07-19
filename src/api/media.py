from tempfile import SpooledTemporaryFile
from uuid import UUID

import filetype
from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.errors import AppError
from src.db.models import Media
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, get_optional_auth, require_csrf
from src.modules.media.schemas import MediaPurpose, MediaRead
from src.modules.media.service import as_read, delete_media, owned_media, upload_media
from src.modules.media.storage import S3Storage

router = APIRouter(prefix="/api/v1/media", tags=["media"])


def get_storage(settings: Settings = Depends(get_settings)) -> S3Storage:
    return S3Storage(settings)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MediaRead)
async def upload(file: UploadFile = File(...), purpose: MediaPurpose = Form(...), auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session), storage: S3Storage = Depends(get_storage)) -> MediaRead:
    max_size = 5 * 1024 * 1024 if purpose == "avatar" else 100 * 1024 * 1024
    with SpooledTemporaryFile(max_size=1024 * 1024) as stream:
        header = await file.read(8_192)
        mime_type = filetype.guess_mime(header)
        stream.write(header)
        size_bytes = len(header)
        if mime_type and mime_type.startswith("image/"):
            max_size = min(max_size, 10 * 1024 * 1024)
        while chunk := await file.read(64 * 1024):
            size_bytes += len(chunk)
            if size_bytes > max_size:
                raise AppError("MEDIA_TOO_LARGE", "Media exceeds its size limit", 413)
            stream.write(chunk)
        stream.seek(0)
        try:
            media = await upload_media(session, storage, auth.user.id, purpose, stream, mime_type, size_bytes)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    await session.refresh(media)
    return as_read(media)


@router.get("/{media_id}")
async def download(media_id: UUID, auth: CurrentAuth | None = Depends(get_optional_auth), session: AsyncSession = Depends(get_session), storage: S3Storage = Depends(get_storage)) -> StreamingResponse:
    media = await session.get(Media, media_id)
    if media is None or media.deleted_at is not None or media.status == "uploaded" and (auth is None or auth.user.id != media.owner_id):
        raise AppError("RESOURCE_NOT_FOUND", "Media not found", 404)
    result = await storage.get(media.storage_key)
    return StreamingResponse(result["Body"].iter_chunks(), media_type=media.mime_type, headers={"Content-Disposition": "attachment", "X-Content-Type-Options": "nosniff"})


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def remove(media_id: UUID, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session), storage: S3Storage = Depends(get_storage)) -> Response:
    await delete_media(session, storage, await owned_media(session, media_id, auth.user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
