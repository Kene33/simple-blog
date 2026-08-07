import asyncio
from collections import defaultdict
from collections.abc import Awaitable
from typing import Any
from uuid import UUID


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
