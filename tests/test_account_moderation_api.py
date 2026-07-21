from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import User


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_admin_can_mute_ban_and_restore_user(client: AsyncClient) -> None:
    admin_csrf = await register(client, "adminmoderator")
    target = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        target_csrf = await register(target, "muteduser")
        async with client._transport.app.state.session_factory() as session:
            admin = await session.scalar(select(User).where(User.username_normalized == "adminmoderator"))
            target_user = await session.scalar(select(User).where(User.username_normalized == "muteduser"))
            admin.role = "admin"
            await session.commit()
        users = await client.get("/api/v1/admin/users", params={"query": "muted"})
        assert users.status_code == 200
        assert users.json()[0]["id"] == str(target_user.id)
        mute = await client.patch(f"/api/v1/admin/users/{target_user.id}/moderation", json={"action": "mute", "muted_until": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(), "reason": "Spam"}, headers={"X-CSRF-Token": admin_csrf})
        assert mute.status_code == 200
        blocked = await target.post("/api/v1/posts", json={"title": "No", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": target_csrf})
        assert blocked.status_code == 403
        assert (await client.patch(f"/api/v1/admin/users/{target_user.id}/moderation", json={"action": "unmute"}, headers={"X-CSRF-Token": admin_csrf})).status_code == 200
        assert (await client.patch(f"/api/v1/admin/users/{target_user.id}/moderation", json={"action": "ban", "reason": "Repeated spam"}, headers={"X-CSRF-Token": admin_csrf})).status_code == 200
        assert (await target.get("/api/v1/users/me")).status_code == 401
        assert (await client.patch(f"/api/v1/admin/users/{target_user.id}/moderation", json={"action": "unban"}, headers={"X-CSRF-Token": admin_csrf})).status_code == 200
        assert (await target.post("/api/v1/auth/login", json={"identifier": "muteduser", "password": "strong-password"})).status_code == 200
    finally:
        await target.aclose()
