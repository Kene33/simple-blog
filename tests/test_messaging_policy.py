from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.errors import AppError
from src.db.base import Base
from src.db.models import User, UserBlock
from src.modules.messaging.policy import assert_can_contact


async def make_users(session: AsyncSession) -> tuple[User, User]:
    first = User(username="firstuser", username_normalized="firstuser", email="first@example.com", email_normalized="first@example.com", password_hash="test")
    second = User(username="seconduser", username_normalized="seconduser", email="second@example.com", email_normalized="second@example.com", password_hash="test")
    session.add_all([first, second])
    await session.flush()
    return first, second


@pytest.mark.asyncio
async def test_messaging_policy_rejects_blocked_banned_and_muted_users() -> None:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        first, second = await make_users(session)
        await assert_can_contact(session, first, second)

        session.add(UserBlock(blocker_id=second.id, blocked_id=first.id))
        await session.flush()
        with pytest.raises(AppError, match="not available"):
            await assert_can_contact(session, first, second)

        await session.delete(await session.get(UserBlock, (second.id, first.id)))
        second.status = "banned"
        with pytest.raises(AppError, match="not available"):
            await assert_can_contact(session, first, second)

        second.status = "active"
        first.muted_until = datetime.now(timezone.utc) + timedelta(minutes=5)
        with pytest.raises(AppError, match="muted"):
            await assert_can_contact(session, first, second)
    await engine.dispose()
