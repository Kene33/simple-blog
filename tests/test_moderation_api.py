import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import User


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_reports_validate_target_and_prevent_open_duplicates(client: AsyncClient) -> None:
    csrf = await register(client, "reporter")
    post = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    post_id = post.json()["id"]
    report = await client.post("/api/v1/reports", json={"post_id": post_id, "reason": "spam"}, headers={"X-CSRF-Token": csrf})
    assert report.status_code == 201
    duplicate = await client.post("/api/v1/reports", json={"post_id": post_id, "reason": "spam"}, headers={"X-CSRF-Token": csrf})
    assert duplicate.status_code == 409
    invalid = await client.post("/api/v1/reports", json={"reason": "spam"}, headers={"X-CSRF-Token": csrf})
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_admin_can_process_reports(client: AsyncClient) -> None:
    admin_csrf = await register(client, "adminuser")
    async with client._transport.app.state.session_factory() as session:
        admin = await session.scalar(select(User).where(User.username_normalized == "adminuser"))
        admin.role = "admin"
        await session.commit()
    post = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": admin_csrf})
    report = await client.post("/api/v1/reports", json={"post_id": post.json()["id"], "reason": "spam"}, headers={"X-CSRF-Token": admin_csrf})
    queue = await client.get("/api/v1/admin/reports")
    assert queue.status_code == 200
    assert queue.json()["items"][0]["id"] == report.json()["id"]
    processed = await client.patch(f"/api/v1/admin/reports/{report.json()['id']}", json={"status": "resolved", "resolution": "Handled"})
    assert processed.status_code == 200
    assert processed.json()["status"] == "resolved"
