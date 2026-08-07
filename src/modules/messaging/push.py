import asyncio
import json
import logging
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.db.models import PushSubscription

logger = logging.getLogger(__name__)


async def save_subscription(session: AsyncSession, user_id: UUID, endpoint: str, p256dh: str, auth: str) -> PushSubscription:
    subscription = await session.scalar(select(PushSubscription).where(PushSubscription.endpoint == endpoint))
    if subscription is None:
        subscription = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh=p256dh, auth=auth)
        session.add(subscription)
    else:
        subscription.user_id = user_id
        subscription.p256dh = p256dh
        subscription.auth = auth
    await session.flush()
    return subscription


async def remove_subscription(session: AsyncSession, user_id: UUID, endpoint: str) -> None:
    await session.execute(delete(PushSubscription).where(PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint))


async def send_push_notifications(session: AsyncSession, user_ids: list[UUID], title: str, body: str, settings: Settings) -> None:
    if not settings.vapid_private_key or not settings.vapid_subject or not user_ids:
        return
    subscriptions = (await session.scalars(select(PushSubscription).where(PushSubscription.user_id.in_(user_ids)))).all()
    if not subscriptions:
        return
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("Push notifications are configured but pywebpush is not installed")
        return

    payload = {"title": title, "body": body}
    for subscription in subscriptions:
        try:
            await asyncio.to_thread(webpush, subscription_info={"endpoint": subscription.endpoint, "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth}}, data=json.dumps(payload), vapid_private_key=settings.vapid_private_key, vapid_claims={"sub": settings.vapid_subject})
        except WebPushException as error:
            if getattr(error, "response", None) is not None and getattr(error.response, "status_code", None) in {404, 410}:
                await session.delete(subscription)
            else:
                logger.warning("Push delivery failed", extra={"subscription_id": str(subscription.id)})
