import asyncio
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import Request

from src.core.errors import AppError


class RateLimiter:
    def __init__(self, redis_url: str | None) -> None:
        self._redis_url = redis_url
        self._redis: Any = None
        self._lock = asyncio.Lock()
        self._local: dict[str, deque[float]] = defaultdict(deque)

    async def check(self, request: Request, bucket: str, limit: int, window: int, identity: str | None = None) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"rate:{bucket}:{ip}:{identity or '-'}"
        if self._redis_url:
            await self._check_redis(key, limit, window)
            return
        now = time.monotonic()
        async with self._lock:
            hits = self._local[key]
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                raise AppError("RATE_LIMITED", "Too many requests", 429)
            hits.append(now)

    async def _check_redis(self, key: str, limit: int, window: int) -> None:
        try:
            if self._redis is None:
                from redis.asyncio import from_url

                self._redis = from_url(self._redis_url, decode_responses=True)
            hits = await self._redis.incr(key)
            if hits == 1:
                await self._redis.expire(key, window)
            if hits > limit:
                raise AppError("RATE_LIMITED", "Too many requests", 429)
        except AppError:
            raise
        except Exception as error:
            raise AppError("RATE_LIMIT_UNAVAILABLE", "Request protection is temporarily unavailable", 503) from error

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
