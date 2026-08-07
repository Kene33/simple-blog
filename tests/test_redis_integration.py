import asyncio
import os
from uuid import uuid4

import pytest

from src.core.realtime import RealtimeHub, RedisRealtimeBridge


class Socket:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    async def send_json(self, event: dict[str, object]) -> None:
        self.events.append(event)


@pytest.mark.asyncio
@pytest.mark.redis
async def test_redis_delivers_message_between_two_realtime_instances() -> None:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL is not configured")
    from redis.asyncio import from_url

    user_id = uuid4()
    hub_a = RealtimeHub()
    hub_b = RealtimeHub()
    socket = Socket()
    await hub_b.connect(user_id, socket)
    client_a = from_url(redis_url, decode_responses=True)
    client_b = from_url(redis_url, decode_responses=True)
    bridge_a = RedisRealtimeBridge(redis_url, hub_a, redis_client=client_a)
    bridge_b = RedisRealtimeBridge(redis_url, hub_b, redis_client=client_b)
    try:
        await bridge_a.start()
        await bridge_b.start()
        await bridge_a.publish(user_id, {"type": "message.created", "conversation_id": str(uuid4())})
        for _ in range(30):
            if socket.events:
                break
            await asyncio.sleep(0.05)
        assert socket.events and socket.events[0]["type"] == "message.created"
    finally:
        await bridge_a.close()
        await bridge_b.close()
