from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.lifecycle = "running"
    await app.state.realtime_bridge.start()
    yield
    await app.state.realtime_bridge.close()
    if getattr(app.state, "rate_limiter", None) is not None:
        await app.state.rate_limiter.close()
    await engine.dispose()
    app.state.lifecycle = "stopped"
