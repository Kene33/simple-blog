from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.config import Settings, get_settings
from src.api.media import get_storage
from src.db.base import Base
from src.db.session import get_session
from src.main import create_app


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}

    def key_for(self, owner_id: object, mime_type: str) -> str:
        return f"uploads/{owner_id}/{len(self.objects)}.{mime_type.rsplit('/', 1)[1]}"

    async def put(self, key: str, content: bytes, mime_type: str) -> None:
        self.objects[key] = (content, mime_type)

    async def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    async def get(self, key: str) -> dict[str, object]:
        content, _ = self.objects[key]

        class Body:
            def iter_chunks(self) -> list[bytes]:
                return [content]

        return {"Body": Body()}


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
async def client(storage: FakeStorage) -> AsyncIterator[AsyncClient]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    settings = Settings(reload=False, jwt_secret_key="test-secret-that-is-long-enough-for-auth", database_url="sqlite+aiosqlite://")
    application = create_app(settings)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_storage] = lambda: storage
    application.state.session_factory = session_factory
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://testserver") as api_client:
        yield api_client
    await engine.dispose()
