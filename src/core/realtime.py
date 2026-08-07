import asyncio
import json
import logging
from collections import defaultdict
from collections.abc import Awaitable
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class RealtimeHub:
    # ponytail: process-local hub; Redis Pub/Sub in DM-B5 for multi-instance delivery.
    def __init__(self) -> None:
        self._connections: dict[UUID, set[Any]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID, websocket: Any) -> None:
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: UUID, websocket: Any) -> None:
        async with self._lock:
            connections = self._connections.get(user_id)
            if connections is None:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(user_id, None)

    async def publish(self, user_id: UUID, event: dict[str, object]) -> None:
        async with self._lock:
            sockets = tuple(self._connections.get(user_id, ()))
        results: list[Awaitable[None]] = [socket.send_json(event) for socket in sockets]
        if not results:
            return
        outcomes = await asyncio.gather(*results, return_exceptions=True)
        for websocket, outcome in zip(sockets, outcomes, strict=True):
            if isinstance(outcome, Exception):
                await self.disconnect(user_id, websocket)


class RedisRealtimeBridge:
    channel = "simple-blog:messaging"

    def __init__(self, redis_url: str | None, hub: RealtimeHub, redis_client: Any = None) -> None:
        self._redis_url = redis_url
        self._hub = hub
        self._redis = redis_client
        self._pubsub: Any = None
        self._task: asyncio.Task[None] | None = None
        self._instance_id = uuid4().hex

    async def start(self) -> None:
        if not self._redis_url and self._redis is None:
            return
        if self._redis is None:
            from redis.asyncio import from_url

            self._redis = from_url(self._redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(self.channel)
        self._task = asyncio.create_task(self._listen())

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self._pubsub is not None:
            await self._pubsub.close()
            self._pubsub = None
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def publish(self, user_id: UUID, event: dict[str, object]) -> None:
        await self._hub.publish(user_id, event)
        if self._redis is None:
            return
        payload = json.dumps({"origin": self._instance_id, "user_id": str(user_id), "event": event}, separators=(",", ":"))
        try:
            await self._redis.publish(self.channel, payload)
        except Exception:
            logger.exception("Realtime event publish failed")

    async def _listen(self) -> None:
        while True:
            try:
                message = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    await asyncio.sleep(0.05)
                    continue
                payload = json.loads(message["data"])
                if payload["origin"] != self._instance_id:
                    await self._hub.publish(UUID(payload["user_id"]), payload["event"])
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Realtime event subscription failed")
                await asyncio.sleep(1)
