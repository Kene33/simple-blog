import pytest

from src.core.rate_limit import RateLimiter


class FakeRedis:
    def __init__(self, healthy: bool) -> None:
        self.healthy = healthy

    async def ping(self) -> bool:
        if not self.healthy:
            raise ConnectionError("redis unavailable")
        return True

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_rate_limiter_ping_is_available_without_redis() -> None:
    assert await RateLimiter(None).ping() is True


@pytest.mark.asyncio
async def test_rate_limiter_ping_reports_redis_health() -> None:
    healthy = RateLimiter("redis://test")
    healthy._redis = FakeRedis(True)
    unhealthy = RateLimiter("redis://test")
    unhealthy._redis = FakeRedis(False)

    assert await healthy.ping() is True
    assert await unhealthy.ping() is False
