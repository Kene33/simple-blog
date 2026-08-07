from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.db.base import Base
from src.db.models import Conversation, ConversationMember, Message, User
from src.modules.messaging.service import purge_deleted_messages


@pytest.mark.asyncio
async def test_direct_conversation_persists_members_and_messages() -> None:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        first = User(username="firstuser", username_normalized="firstuser", email="first@example.com", email_normalized="first@example.com", password_hash="test")
        second = User(username="seconduser", username_normalized="seconduser", email="second@example.com", email_normalized="second@example.com", password_hash="test")
        session.add_all([first, second])
        await session.flush()
        direct_key = ":".join(sorted((str(first.id), str(second.id))))
        conversation = Conversation(direct_key=direct_key)
        session.add(conversation)
        await session.flush()
        session.add_all([ConversationMember(conversation_id=conversation.id, user_id=first.id), ConversationMember(conversation_id=conversation.id, user_id=second.id)])
        message = Message(conversation_id=conversation.id, sender_id=first.id, body="hello")
        session.add(message)
        await session.commit()

        stored = await session.scalar(select(Message).where(Message.id == message.id))
        assert stored is not None
        assert stored.body == "hello"
        assert stored.sender_id == first.id

        session.add(Conversation(direct_key=direct_key))
        with pytest.raises(IntegrityError):
            await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_deleted_messages_are_purged_only_after_retention_cutoff() -> None:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        first = User(username="retentionfirst", username_normalized="retentionfirst", email="retentionfirst@example.com", email_normalized="retentionfirst@example.com", password_hash="test")
        second = User(username="retentionsecond", username_normalized="retentionsecond", email="retentionsecond@example.com", email_normalized="retentionsecond@example.com", password_hash="test")
        session.add_all([first, second])
        await session.flush()
        conversation = Conversation(direct_key=":".join(sorted((str(first.id), str(second.id)))))
        session.add(conversation)
        await session.flush()
        session.add_all([ConversationMember(conversation_id=conversation.id, user_id=first.id), ConversationMember(conversation_id=conversation.id, user_id=second.id)])
        old = Message(conversation_id=conversation.id, sender_id=first.id, body="old", deleted_at=datetime.now(timezone.utc) - timedelta(days=400))
        recent = Message(conversation_id=conversation.id, sender_id=first.id, body="recent", deleted_at=datetime.now(timezone.utc) - timedelta(days=2))
        session.add_all([old, recent])
        await session.commit()

        deleted = await purge_deleted_messages(session, datetime.now(timezone.utc) - timedelta(days=30))
        await session.commit()

        assert deleted == 1
        assert await session.get(Message, old.id) is None
        assert await session.get(Message, recent.id) is not None
    await engine.dispose()
