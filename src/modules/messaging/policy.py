from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import AppError
from src.db.models import User, UserBlock


def _future(value: datetime | None) -> bool:
    if value is None:
        return False
    current = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return current > datetime.now(timezone.utc)


async def assert_can_contact(session: AsyncSession, actor: User, target: User) -> None:
    if actor.id == target.id or actor.status != "active" or actor.disabled_at is not None:
        raise AppError("FORBIDDEN", "Messaging is not available", 403)
    if target.status != "active" or target.disabled_at is not None:
        raise AppError("RESOURCE_NOT_FOUND", "Messaging target is not available", 404)
    if _future(actor.muted_until):
        raise AppError("USER_MUTED", "User is muted", 403)
    blocked = await session.scalar(select(UserBlock.blocker_id).where(or_(UserBlock.blocker_id == actor.id, UserBlock.blocker_id == target.id), or_(UserBlock.blocked_id == actor.id, UserBlock.blocked_id == target.id)))
    if blocked is not None:
        raise AppError("RESOURCE_NOT_FOUND", "Messaging target is not available", 404)
