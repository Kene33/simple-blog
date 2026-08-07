from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.errors import AppError
from src.db.models import User
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, get_current_auth, get_websocket_auth, require_csrf, require_unmuted_csrf
from src.modules.messaging.schemas import ConversationPage, ConversationRead, ConversationReadMarker, MessageCreateRequest, MessagePage, MessageRead, MessageUpdateRequest
from src.modules.messaging.service import (
    block_user,
    create_message,
    delete_message,
    get_or_create_direct,
    list_conversations,
    list_messages,
    mark_read,
    recipient_id,
    serialize_conversation,
    serialize_message,
    unblock_user,
    update_message,
)

router = APIRouter(tags=["messaging"])


@router.post("/api/v1/conversations/direct/{user_id}", response_model=ConversationRead)
async def create_direct(user_id: UUID, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> ConversationRead:
    target = await session.scalar(select(User).where(User.id == user_id))
    if target is None:
        raise AppError("RESOURCE_NOT_FOUND", "User not found", 404)
    conversation = await get_or_create_direct(session, auth.user, target)
    await session.commit()
    return await serialize_conversation(session, conversation, auth.user.id)


@router.get("/api/v1/conversations", response_model=ConversationPage)
async def conversations(cursor: str | None = None, limit: int = 20, auth: CurrentAuth = Depends(get_current_auth), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> ConversationPage:
    return await list_conversations(session, auth.user.id, settings, cursor, min(max(limit, 1), 50))


@router.get("/api/v1/conversations/{conversation_id}/messages", response_model=MessagePage)
async def messages(conversation_id: UUID, cursor: str | None = None, limit: int = 50, auth: CurrentAuth = Depends(get_current_auth), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> MessagePage:
    return await list_messages(session, conversation_id, auth.user.id, settings, cursor, min(max(limit, 1), 100))


@router.post("/api/v1/conversations/{conversation_id}/messages", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def send_message(conversation_id: UUID, payload: MessageCreateRequest, request: Request, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> MessageRead:
    await request.app.state.rate_limiter.check(request, "message-create", 30, 600, str(auth.user.id))
    await request.app.state.rate_limiter.check(request, "message-create", 60, 600)
    message = await create_message(session, conversation_id, auth.user, payload)
    target_id = await recipient_id(session, conversation_id, auth.user.id)
    await session.commit()
    await session.refresh(message)
    response = await serialize_message(session, message)
    await request.app.state.realtime_hub.publish(target_id, {"type": "message.created", "data": response.model_dump(mode="json")})
    return response


@router.patch("/api/v1/conversations/{conversation_id}/read", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def read_conversation(conversation_id: UUID, payload: ConversationReadMarker, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    await mark_read(session, conversation_id, auth.user.id, payload.message_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/api/v1/messages/{message_id}", response_model=MessageRead)
async def edit_message(message_id: UUID, payload: MessageUpdateRequest, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> MessageRead:
    message = await update_message(session, message_id, auth.user, payload)
    await session.commit()
    await session.refresh(message)
    return await serialize_message(session, message)


@router.delete("/api/v1/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def remove_message(message_id: UUID, auth: CurrentAuth = Depends(require_unmuted_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    await delete_message(session, message_id, auth.user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/v1/users/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def block(user_id: UUID, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    await block_user(session, auth.user, user_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/api/v1/users/{user_id}/block", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def unblock(user_id: UUID, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> Response:
    await unblock_user(session, auth.user, user_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.websocket("/api/v1/ws")
async def websocket_messages(websocket: WebSocket, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> None:
    try:
        auth = await get_websocket_auth(websocket, session, settings)
    except AppError as error:
        await websocket.close(code=4401 if error.status_code == 401 else 4403)
        return
    hub = websocket.app.state.realtime_hub
    await websocket.accept()
    await hub.connect(auth.user.id, websocket)
    try:
        while True:
            event = await websocket.receive_json()
            if event.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.close(code=4400)
                return
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(auth.user.id, websocket)
