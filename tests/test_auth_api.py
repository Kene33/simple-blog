from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.core.config import Settings, get_settings
from src.db.base import Base
from src.db.session import get_session
from src.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
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
    async with AsyncClient(transport=ASGITransport(app=application), base_url="http://testserver") as api_client:
        yield api_client
    await engine.dispose()


@pytest.mark.asyncio
async def test_auth_lifecycle_and_csrf(client: AsyncClient) -> None:
    register = await client.post("/api/v1/auth/register", json={"username": "Alice_1", "email": "Alice@example.com", "password": "strong-password"})
    assert register.status_code == 201
    assert "httponly" in register.headers["set-cookie"].lower()
    assert "access_token" not in register.json()

    csrf = client.cookies.get("csrf_token")
    assert csrf
    me = await client.get("/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == "Alice@example.com"

    rejected_update = await client.patch("/api/v1/users/me", json={"username": "alice_new"})
    assert rejected_update.status_code == 403
    updated = await client.patch("/api/v1/users/me", json={"username": "alice_new"}, headers={"X-CSRF-Token": csrf})
    assert updated.status_code == 200
    assert updated.json()["username"] == "alice_new"

    old_refresh = client.cookies.get("refresh_token")
    old_csrf = client.cookies.get("csrf_token")
    refreshed = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert refreshed.status_code == 200
    assert client.cookies.get("refresh_token") != old_refresh

    client.cookies.set("refresh_token", old_refresh)
    client.cookies.set("csrf_token", old_csrf)
    replay = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "AUTH_INVALID"


@pytest.mark.asyncio
async def test_duplicate_identity_and_profile_privacy(client: AsyncClient) -> None:
    payload = {"username": "alice", "email": "alice@example.com", "password": "strong-password"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    duplicate = await client.post("/api/v1/auth/register", json={**payload, "email": "ALICE@example.com"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "RESOURCE_CONFLICT"

    public = await client.get("/api/v1/users/ALICE")
    assert public.status_code == 200
    assert "email" not in public.json()
    assert "role" not in public.json()


@pytest.mark.asyncio
async def test_missing_refresh_csrf_and_logout(client: AsyncClient) -> None:
    missing_refresh = await client.post("/api/v1/auth/refresh")
    assert missing_refresh.status_code == 401
    assert missing_refresh.json()["error"]["code"] == "AUTH_REQUIRED"

    payload = {"username": "alice", "email": "alice@example.com", "password": "strong-password"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    invalid_csrf = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "wrong"})
    assert invalid_csrf.status_code == 403
    assert invalid_csrf.json()["error"]["code"] == "CSRF_FAILED"

    csrf = client.cookies.get("csrf_token")
    logout = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 204
    assert (await client.get("/api/v1/users/me")).status_code == 401
