from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, get_current_auth, require_unmuted_csrf
from src.modules.posts.schemas import DraftCreateRequest, DraftPage, DraftRead, DraftUpdateRequest, PostRead
from src.modules.posts.service import create_draft, delete_draft, get_draft, list_drafts, publish_draft, serialize_draft, serialize_post, update_draft

router = APIRouter(prefix="/api/v1/drafts", tags=["drafts"])


@router.post("", response_model=DraftRead, status_code=status.HTTP_201_CREATED)
async def create(payload: DraftCreateRequest, request: Request, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> DraftRead:
    await request.app.state.rate_limiter.check(request, "draft-create", 30, 3600, str(auth.user.id))
    draft = await create_draft(session, auth.user, payload)
    await session.commit()
    await session.refresh(draft)
    return await serialize_draft(session, draft)


@router.get("", response_model=DraftPage)
async def list_all(cursor: str | None = None, limit: int = 20, auth: CurrentAuth = Depends(get_current_auth), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> DraftPage:
    return await list_drafts(session, settings=settings, author_id=auth.user.id, cursor=cursor, limit=min(max(limit, 1), 100))


@router.get("/{draft_id}", response_model=DraftRead)
async def read(draft_id: UUID, auth: CurrentAuth = Depends(get_current_auth), session: AsyncSession = Depends(get_session)) -> DraftRead:
    return await serialize_draft(session, await get_draft(session, draft_id, auth.user.id))


@router.patch("/{draft_id}", response_model=DraftRead)
async def update(draft_id: UUID, payload: DraftUpdateRequest, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> DraftRead:
    draft = await update_draft(session, await get_draft(session, draft_id, auth.user.id), auth.user.id, payload)
    await session.commit()
    await session.refresh(draft)
    return await serialize_draft(session, draft)


@router.post("/{draft_id}/publish", response_model=PostRead)
async def publish(draft_id: UUID, request: Request, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> PostRead:
    await request.app.state.rate_limiter.check(request, "post-publish", 20, 3600, str(auth.user.id))
    draft = await publish_draft(session, await get_draft(session, draft_id, auth.user.id))
    await session.commit()
    await session.refresh(draft)
    return await serialize_post(session, draft, auth.user.id)


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete(draft_id: UUID, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    await delete_draft(session, await get_draft(session, draft_id, auth.user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
