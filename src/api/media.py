from pathlib import PurePath
from tempfile import SpooledTemporaryFile
from uuid import UUID

import filetype
from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.errors import AppError
from src.db.models import ConversationMember, Media, Message, MessageMedia, Post, PostMedia, User
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, get_optional_auth, require_unmuted_csrf
from src.modules.media.schemas import MediaPurpose, MediaRead
from src.modules.media.service import as_read, delete_media, owned_media, upload_media
from src.modules.media.storage import S3Storage

router = APIRouter(prefix="/api/v1/media", tags=["media"])
ALLOWED_EXTENSIONS = {"image/jpeg": {".jpg", ".jpeg"}, "image/png": {".png"}, "image/gif": {".gif"}, "image/webp": {".webp"}, "video/mp4": {".mp4"}, "video/webm": {".webm"}}


def get_storage(settings: Settings = Depends(get_settings)) -> S3Storage:
    return S3Storage(settings)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MediaRead)
async def upload(request: Request, file: UploadFile = File(...), purpose: MediaPurpose = Form(...), auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session), storage: S3Storage = Depends(get_storage), settings: Settings = Depends(get_settings)) -> MediaRead:
    await request.app.state.rate_limiter.check(request, "media-upload", 20, 3600, str(auth.user.id))
    await request.app.state.rate_limiter.check(request, "media-upload", 30, 3600)
    max_size = 5 * 1024 * 1024 if purpose == "avatar" else 100 * 1024 * 1024
    with SpooledTemporaryFile(max_size=1024 * 1024) as stream:
        if not file.filename or PurePath(file.filename).suffix.lower() not in {extension for extensions in ALLOWED_EXTENSIONS.values() for extension in extensions}:
            raise AppError("MEDIA_UNSUPPORTED", "File extension is not allowed", 415)
        header = await file.read(8_192)
        mime_type = filetype.guess_mime(header)
        if mime_type not in ALLOWED_EXTENSIONS or PurePath(file.filename).suffix.lower() not in ALLOWED_EXTENSIONS[mime_type]:
            raise AppError("MEDIA_UNSUPPORTED", "File content and extension do not match", 415)
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
            media = await upload_media(session, storage, auth.user.id, purpose, stream, mime_type, size_bytes, settings)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    await session.refresh(media)
    return as_read(media)


@router.get("/{media_id}")
async def download(media_id: UUID, auth: CurrentAuth | None = Depends(get_optional_auth), session: AsyncSession = Depends(get_session), storage: S3Storage = Depends(get_storage), settings: Settings = Depends(get_settings)) -> StreamingResponse:
    media = await session.get(Media, media_id)
    if media is None or media.deleted_at is not None:
        raise AppError("RESOURCE_NOT_FOUND", "Media not found", 404)
    public = False
    if media.status == "uploaded":
        public = auth is not None and auth.user.id == media.owner_id
    elif media.status == "attached" and media.purpose in {"avatar", "cover"}:
        owner = await session.scalar(select(User).where(User.id == media.owner_id, User.profile_visibility == "public", User.status != "deleted", (User.avatar_media_id == media.id) | (User.cover_media_id == media.id)))
        public = owner is not None
        public = public or auth is not None and auth.user.id == media.owner_id
    elif media.status == "attached":
        post = await session.scalar(select(Post).join(PostMedia, PostMedia.post_id == Post.id).join(User, User.id == Post.author_id).where(PostMedia.media_id == media.id, Post.status == "published", Post.deleted_at.is_(None), User.posts_visibility == "public"))
        public = post is not None or auth is not None and auth.user.id == media.owner_id
        if auth is not None and not public and media.purpose == "message":
            public = await session.scalar(select(ConversationMember.user_id).join(Message, Message.conversation_id == ConversationMember.conversation_id).join(MessageMedia, MessageMedia.message_id == Message.id).where(MessageMedia.media_id == media.id, ConversationMember.user_id == auth.user.id)) is not None
    if not public:
        raise AppError("RESOURCE_NOT_FOUND", "Media not found", 404)
    result = await storage.get(media.storage_key)
    cache = f"public, max-age={settings.media_public_cache_seconds}, stale-while-revalidate=60" if media.status == "attached" and public else "private, no-store"
    return StreamingResponse(result["Body"].iter_chunks(), media_type=media.mime_type, headers={"Content-Disposition": "attachment", "Cache-Control": cache, "X-Content-Type-Options": "nosniff"})


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def remove(media_id: UUID, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session), storage: S3Storage = Depends(get_storage)) -> Response:
    await delete_media(session, storage, await owned_media(session, media_id, auth.user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
