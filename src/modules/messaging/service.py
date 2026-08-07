import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.db.models import Conversation, ConversationMember, Media, Message, MessageMedia, User, UserBlock
from src.modules.auth.service import user_summary
from src.modules.media.service import as_read
from src.modules.messaging.policy import assert_can_contact
from src.modules.messaging.schemas import (
    ConversationMuteRequest,
    ConversationPage,
    ConversationRead,
    GroupCreateRequest,
    MessageCreateRequest,
    MessagePage,
    MessageRead,
    MessageUpdateRequest,
)

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


async def _participants(session: AsyncSession, conversation_id: UUID, user_id: UUID) -> list[User]:
    return (await session.scalars(select(User).join(ConversationMember, ConversationMember.user_id == User.id).where(ConversationMember.conversation_id == conversation_id, User.id != user_id).order_by(User.username_normalized))).all()


async def recipient_id(session: AsyncSession, conversation_id: UUID, user_id: UUID) -> UUID:
    participant = await _participant(session, conversation_id, user_id)
    return participant.id


async def recipient_ids(session: AsyncSession, conversation_id: UUID, user_id: UUID) -> list[UUID]:
    await _member(session, conversation_id, user_id)
    return [participant.id for participant in await _participants(session, conversation_id, user_id)]


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
    conversation = Conversation(direct_key=key, kind="direct", created_by_id=actor.id)
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


async def create_group(session: AsyncSession, actor: User, payload: GroupCreateRequest) -> Conversation:
    member_ids = list(dict.fromkeys(payload.member_ids))
    if actor.id in member_ids:
        member_ids.remove(actor.id)
    if not member_ids:
        raise AppError("VALIDATION_ERROR", "A group needs at least one other member", 422)
    members = (await session.scalars(select(User).where(User.id.in_(member_ids), User.status == "active", User.disabled_at.is_(None)))).all()
    if len(members) != len(member_ids):
        raise AppError("RESOURCE_NOT_FOUND", "A group member was not found", 404)
    for member in members:
        await assert_can_contact(session, actor, member)
    conversation = Conversation(kind="group", title=payload.title, created_by_id=actor.id)
    session.add(conversation)
    await session.flush()
    session.add(ConversationMember(conversation_id=conversation.id, user_id=actor.id, role="admin"))
    session.add_all(ConversationMember(conversation_id=conversation.id, user_id=member.id) for member in members)
    await session.flush()
    return conversation


async def _read_by_recipient(session: AsyncSession, message: Message) -> bool:
    member = await session.scalar(select(ConversationMember).where(ConversationMember.conversation_id == message.conversation_id, ConversationMember.user_id != message.sender_id))
    if member is None or member.last_read_message_id is None:
        return False
    marker = await session.get(Message, member.last_read_message_id)
    return marker is not None and (marker.created_at > message.created_at or (marker.created_at == message.created_at and marker.id >= message.id))


def _is_future(value: datetime | None) -> bool:
    if value is None:
        return False
    normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return normalized > datetime.now(timezone.utc)


async def serialize_message(session: AsyncSession, message: Message) -> MessageRead:
    sender = await session.get(User, message.sender_id)
    if sender is None:
        raise AppError("INTERNAL_ERROR", "Message sender is unavailable", 500)
    media = (await session.scalars(select(Media).join(MessageMedia, MessageMedia.media_id == Media.id).where(MessageMedia.message_id == message.id).order_by(MessageMedia.position))).all()
    return MessageRead(id=message.id, conversation_id=message.conversation_id, sender=user_summary(sender), body=TOMBSTONE_BODY if message.deleted_at else message.body, is_deleted=message.deleted_at is not None, read_by_recipient=await _read_by_recipient(session, message), media=[as_read(item) for item in media], created_at=message.created_at, updated_at=message.updated_at)


async def serialize_conversation(session: AsyncSession, conversation: Conversation, user_id: UUID) -> ConversationRead:
    participants = await _participants(session, conversation.id, user_id)
    if not participants:
        raise AppError("RESOURCE_NOT_FOUND", "Conversation not found", 404)
    participant = participants[0]
    member = await _member(session, conversation.id, user_id)
    last_message = await session.scalar(select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.desc(), Message.id.desc()).limit(1))
    unread_query = select(func.count()).select_from(Message).where(Message.conversation_id == conversation.id, Message.sender_id != user_id, Message.deleted_at.is_(None))
    if member.last_read_message_id is not None:
        marker = await session.get(Message, member.last_read_message_id)
        if marker is not None:
            unread_query = unread_query.where(or_(Message.created_at > marker.created_at, and_(Message.created_at == marker.created_at, Message.id > marker.id)))
    unread_count = await session.scalar(unread_query) or 0
    blocked = await session.scalar(select(UserBlock.blocker_id).where(or_(and_(UserBlock.blocker_id == user_id, UserBlock.blocked_id == participant.id), and_(UserBlock.blocker_id == participant.id, UserBlock.blocked_id == user_id)))) is not None
    return ConversationRead(id=conversation.id, kind=conversation.kind, title=conversation.title, participant=user_summary(participant), participants=[user_summary(item) for item in participants], last_message=await serialize_message(session, last_message) if last_message else None, unread_count=unread_count, muted=_is_future(member.muted_until), blocked=blocked, created_at=conversation.created_at, updated_at=conversation.updated_at)


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
    for target in await _participants(session, conversation_id, actor.id):
        await assert_can_contact(session, actor, target)
    now = datetime.now(timezone.utc)
    message = Message(conversation_id=conversation_id, sender_id=actor.id, body=payload.body, created_at=now, updated_at=now)
    session.add(message)
    await session.execute(update(Conversation).where(Conversation.id == conversation_id).values(updated_at=now))
    await session.flush()
    if payload.media_ids:
        media = (await session.scalars(select(Media).where(Media.id.in_(payload.media_ids), Media.owner_id == actor.id, Media.purpose == "message", Media.status == "uploaded", Media.deleted_at.is_(None)))).all()
        if len(media) != len(set(payload.media_ids)) or sum(item.kind == "video" for item in media) > 1:
            raise AppError("VALIDATION_ERROR", "Message media must be owned active uploads with at most one video", 422)
        for position, media_id in enumerate(payload.media_ids):
            session.add(MessageMedia(message_id=message.id, media_id=media_id, position=position))
        for item in media:
            item.status = "attached"
            item.attached_at = now
        await session.flush()
    return message


async def mark_read(session: AsyncSession, conversation_id: UUID, user_id: UUID, message_id: UUID) -> None:
    member = await _member(session, conversation_id, user_id)
    message = await session.scalar(select(Message).where(Message.id == message_id, Message.conversation_id == conversation_id))
    if message is None:
        raise AppError("RESOURCE_NOT_FOUND", "Message not found", 404)
    member.last_read_message_id = message.id
    await session.flush()


async def mute_conversation(session: AsyncSession, conversation_id: UUID, user_id: UUID, payload: ConversationMuteRequest) -> ConversationMember:
    member = await _member(session, conversation_id, user_id)
    member.muted_until = datetime.now(timezone.utc) + timedelta(days=30) if payload.muted else None
    await session.flush()
    return member


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


async def purge_deleted_messages(session: AsyncSession, older_than: datetime, batch_size: int = 500) -> int:
    rows = (await session.scalars(select(Message.id).where(Message.deleted_at.is_not(None), Message.deleted_at < older_than).order_by(Message.deleted_at, Message.id).limit(batch_size))).all()
    if not rows:
        return 0
    result = await session.execute(delete(Message).where(Message.id.in_(rows)))
    await session.flush()
    return result.rowcount or 0


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
