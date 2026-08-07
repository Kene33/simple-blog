import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.db.models import Conversation, ConversationMember, Message, User, UserBlock
from src.modules.auth.service import user_summary
from src.modules.messaging.policy import assert_can_contact
from src.modules.messaging.schemas import ConversationPage, ConversationRead, MessageCreateRequest, MessagePage, MessageRead, MessageUpdateRequest

TOMBSTONE_BODY = "[deleted]"


def _direct_key(first_id: UUID, second_id: UUID) -> str:
    return ":".join(sorted((str(first_id), str(second_id))))


def _scope(conversation_id: UUID) -> str:
    return hashlib.sha256(f"conversation:{conversation_id}".encode()).hexdigest()


def _encode_cursor(message: Message, scope: str, settings: Settings) -> str:
    payload = {"v": 1, "resource": "messages", "created_at": message.created_at.isoformat(), "id": str(message.id), "scope": scope}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_cursor(value: str, scope: str, settings: Settings) -> tuple[datetime, UUID]:
    try:
        encoded, signature = value.split(".", 1)
        expected = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["v"] != 1 or payload["resource"] != "messages" or payload["scope"] != scope:
            raise ValueError
        return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None


def _encode_conversation_cursor(conversation: Conversation, settings: Settings) -> str:
    payload = {"v": 1, "resource": "conversations", "updated_at": conversation.updated_at.isoformat(), "id": str(conversation.id)}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_conversation_cursor(value: str, settings: Settings) -> tuple[datetime, UUID]:
    try:
        encoded, signature = value.split(".", 1)
        expected = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["v"] != 1 or payload["resource"] != "conversations":
            raise ValueError
        return datetime.fromisoformat(payload["updated_at"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None


async def _member(session: AsyncSession, conversation_id: UUID, user_id: UUID) -> ConversationMember:
    member = await session.scalar(select(ConversationMember).where(ConversationMember.conversation_id == conversation_id, ConversationMember.user_id == user_id))
    if member is None:
        raise AppError("RESOURCE_NOT_FOUND", "Conversation not found", 404)
    return member


async def _participant(session: AsyncSession, conversation_id: UUID, user_id: UUID) -> User:
    participant = await session.scalar(select(User).join(ConversationMember, ConversationMember.user_id == User.id).where(ConversationMember.conversation_id == conversation_id, User.id != user_id))
    if participant is None:
        raise AppError("RESOURCE_NOT_FOUND", "Conversation not found", 404)
    return participant


async def recipient_id(session: AsyncSession, conversation_id: UUID, user_id: UUID) -> UUID:
    participant = await _participant(session, conversation_id, user_id)
    return participant.id


async def message_context(session: AsyncSession, message_id: UUID, user_id: UUID) -> tuple[Message, UUID]:
    message = await session.scalar(select(Message).where(Message.id == message_id, Message.sender_id == user_id))
    if message is None:
        raise AppError("RESOURCE_NOT_FOUND", "Message not found", 404)
    return message, await recipient_id(session, message.conversation_id, user_id)


async def get_or_create_direct(session: AsyncSession, actor: User, target: User) -> Conversation:
    await assert_can_contact(session, actor, target)
    key = _direct_key(actor.id, target.id)
    conversation = await session.scalar(select(Conversation).where(Conversation.direct_key == key))
    if conversation is not None:
        return conversation
    conversation = Conversation(direct_key=key)
    session.add(conversation)
    await session.flush()
    session.add_all([ConversationMember(conversation_id=conversation.id, user_id=actor.id), ConversationMember(conversation_id=conversation.id, user_id=target.id)])
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        conversation = await session.scalar(select(Conversation).where(Conversation.direct_key == key))
        if conversation is None:
            raise
    return conversation


async def serialize_message(session: AsyncSession, message: Message) -> MessageRead:
    sender = await session.get(User, message.sender_id)
    if sender is None:
        raise AppError("INTERNAL_ERROR", "Message sender is unavailable", 500)
    return MessageRead(id=message.id, conversation_id=message.conversation_id, sender=user_summary(sender), body=TOMBSTONE_BODY if message.deleted_at else message.body, is_deleted=message.deleted_at is not None, created_at=message.created_at, updated_at=message.updated_at)


async def serialize_conversation(session: AsyncSession, conversation: Conversation, user_id: UUID) -> ConversationRead:
    participant = await _participant(session, conversation.id, user_id)
    member = await _member(session, conversation.id, user_id)
    last_message = await session.scalar(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc(), Message.id.desc()).limit(1))
    unread_query = select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id, Message.sender_id != user_id, Message.deleted_at.is_(None))
    if member.last_read_message_id is not None:
        marker = await session.get(Message, member.last_read_message_id)
        if marker is not None:
            unread_query = unread_query.where(or_(Message.created_at > marker.created_at, and_(Message.created_at == marker.created_at, Message.id > marker.id)))
    unread_count = await session.scalar(unread_query) or 0
    return ConversationRead(id=conversation.id, participant=user_summary(participant), last_message=await serialize_message(session, last_message) if last_message else None, unread_count=unread_count, created_at=conversation.created_at, updated_at=conversation.updated_at)


async def list_conversations(session: AsyncSession, user_id: UUID, settings: Settings, cursor: str | None, limit: int) -> ConversationPage:
    query = select(Conversation).join(ConversationMember, ConversationMember.conversation_id == Conversation.id).where(ConversationMember.user_id == user_id)
    if cursor:
        created_at, conversation_id = _decode_conversation_cursor(cursor, settings)
        query = query.where(or_(Conversation.updated_at < created_at, and_(Conversation.updated_at == created_at, Conversation.id < conversation_id)))
    rows = (await session.scalars(query.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(limit + 1))).all()
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = _encode_conversation_cursor(last, settings)
    return ConversationPage(items=[await serialize_conversation(session, row, user_id) for row in rows[:limit]], next_cursor=next_cursor)


async def list_messages(session: AsyncSession, conversation_id: UUID, user_id: UUID, settings: Settings, cursor: str | None, limit: int) -> MessagePage:
    await _member(session, conversation_id, user_id)
    scope = _scope(conversation_id)
    query = select(Message).where(Message.conversation_id == conversation_id)
    if cursor:
        created_at, message_id = _decode_cursor(cursor, scope, settings)
        query = query.where(or_(Message.created_at > created_at, and_(Message.created_at == created_at, Message.id > message_id)))
    rows = (await session.scalars(query.order_by(Message.created_at, Message.id).limit(limit + 1))).all()
    next_cursor = _encode_cursor(rows[limit - 1], scope, settings) if len(rows) > limit else None
    return MessagePage(items=[await serialize_message(session, row) for row in rows[:limit]], next_cursor=next_cursor)


async def create_message(session: AsyncSession, conversation_id: UUID, actor: User, payload: MessageCreateRequest) -> Message:
    await _member(session, conversation_id, actor.id)
    target = await _participant(session, conversation_id, actor.id)
    await assert_can_contact(session, actor, target)
    now = datetime.now(timezone.utc)
    message = Message(conversation_id=conversation_id, sender_id=actor.id, body=payload.body, created_at=now, updated_at=now)
    session.add(message)
    await session.execute(update(Conversation).where(Conversation.id == conversation_id).values(updated_at=now))
    await session.flush()
    return message


async def mark_read(session: AsyncSession, conversation_id: UUID, user_id: UUID, message_id: UUID) -> None:
    member = await _member(session, conversation_id, user_id)
    message = await session.scalar(select(Message).where(Message.id == message_id, Message.conversation_id == conversation_id))
    if message is None:
        raise AppError("RESOURCE_NOT_FOUND", "Message not found", 404)
    member.last_read_message_id = message.id
    await session.flush()


async def update_message(session: AsyncSession, message_id: UUID, actor: User, payload: MessageUpdateRequest) -> Message:
    message = await session.scalar(select(Message).where(Message.id == message_id, Message.sender_id == actor.id, Message.deleted_at.is_(None)))
    if message is None:
        raise AppError("RESOURCE_NOT_FOUND", "Message not found", 404)
    message.body = payload.body
    message.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return message


async def delete_message(session: AsyncSession, message_id: UUID, actor: User) -> None:
    result = await session.execute(update(Message).where(Message.id == message_id, Message.sender_id == actor.id, Message.deleted_at.is_(None)).values(deleted_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
    if result.rowcount != 1:
        raise AppError("RESOURCE_NOT_FOUND", "Message not found", 404)


async def block_user(session: AsyncSession, actor: User, target_id: UUID) -> None:
    if actor.id == target_id:
        raise AppError("VALIDATION_ERROR", "A user cannot block themselves", 422)
    target = await session.get(User, target_id)
    if target is None or target.status == "deleted":
        raise AppError("RESOURCE_NOT_FOUND", "User not found", 404)
    if await session.get(UserBlock, (actor.id, target.id)) is None:
        session.add(UserBlock(blocker_id=actor.id, blocked_id=target.id))
        await session.flush()


async def unblock_user(session: AsyncSession, actor: User, target_id: UUID) -> None:
    await session.execute(delete(UserBlock).where(UserBlock.blocker_id == actor.id, UserBlock.blocked_id == target_id))
