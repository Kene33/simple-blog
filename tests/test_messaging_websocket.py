from uuid import uuid4

import pytest

from src.core.config import Settings
from src.core.errors import AppError
from src.core.realtime import RealtimeHub, RedisRealtimeBridge
from src.modules.auth.dependencies import get_websocket_auth


class FakeWebSocket:
    def __init__(self, origin: str | None = None) -> None:
        self.events: list[dict[str, object]] = []
        self.headers = {"origin": origin} if origin else {}
        self.cookies: dict[str, str] = {}

    async def send_json(self, event: dict[str, object]) -> None:
        self.events.append(event)


class FakePubSub:
    async def subscribe(self, channel: str) -> None:
        self.channel = channel

    async def get_message(self, ignore_subscribe_messages: bool, timeout: float) -> None:
        return None

    async def close(self) -> None:
        return None


class FakeRedis:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []
        self.pubsub_client = FakePubSub()

    def pubsub(self) -> FakePubSub:
        return self.pubsub_client

    async def publish(self, channel: str, payload: str) -> None:
        self.published.append((channel, payload))

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_realtime_hub_delivers_only_to_registered_user() -> None:
    hub = RealtimeHub()
    user_id = uuid4()
    other_id = uuid4()
    socket = FakeWebSocket()
    await hub.connect(user_id, socket)

    await hub.publish(other_id, {"type": "message.created"})
    assert socket.events == []
    await hub.publish(user_id, {"type": "message.created"})
    assert socket.events == [{"type": "message.created"}]

    await hub.disconnect(user_id, socket)
    await hub.publish(user_id, {"type": "message.created"})
    assert len(socket.events) == 1


@pytest.mark.asyncio
async def test_websocket_rejects_untrusted_origin_before_authentication() -> None:
    settings = Settings(environment="production", jwt_secret_key="a" * 32, cookie_secure=True, cors_origins="https://simple.example", public_base_url="https://simple.example", smtp_host="smtp.example.com", smtp_from="noreply@example.com", redis_url="redis://localhost:6379/0", cron_secret="cron-secret")
    with pytest.raises(AppError, match="origin"):
        await get_websocket_auth(FakeWebSocket("https://evil.example"), object(), settings)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_redis_bridge_publishes_after_local_delivery() -> None:
    hub = RealtimeHub()
    user_id = uuid4()
    socket = FakeWebSocket()
    await hub.connect(user_id, socket)
    redis = FakeRedis()
    bridge = RedisRealtimeBridge("redis://test", hub, redis_client=redis)
    await bridge.start()
    await bridge.publish(user_id, {"type": "message.created"})
    assert socket.events == [{"type": "message.created"}]
    assert redis.published[0][0] == "simple-blog:messaging"
    await bridge.close()
