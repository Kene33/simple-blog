import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import User


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_category_request_holds_then_publishes_post(client: AsyncClient) -> None:
    csrf = await register(client, "categoryuser")
    request = await client.post("/api/v1/category-requests", json={"name": "Science"}, headers={"X-CSRF-Token": csrf})
    assert request.status_code == 201
    post = await client.post("/api/v1/posts", json={"title": "Pending", "content": "content", "category_request_id": request.json()["id"]}, headers={"X-CSRF-Token": csrf})
    assert post.status_code == 201
    assert post.json()["status"] == "pending_category"
    assert (await client.get("/api/v1/posts")).json()["items"] == []

    async with client._transport.app.state.session_factory() as session:
        admin = await session.scalar(select(User).where(User.username_normalized == "categoryuser"))
        admin.role = "admin"
        await session.commit()
    approved = await client.patch(f"/api/v1/admin/category-requests/{request.json()['id']}", json={"status": "approved"}, headers={"X-CSRF-Token": csrf})
    assert approved.status_code == 200
    assert (await client.get(f"/api/v1/posts/{post.json()['id']}")).json()["status"] == "published"
    assert (await client.get("/api/v1/categories")).json()[0]["name"] == "Science"


@pytest.mark.asyncio
async def test_rejected_category_returns_pending_post_to_drafts(client: AsyncClient) -> None:
    csrf = await register(client, "rejectcategory")
    request = await client.post("/api/v1/category-requests", json={"name": "Rejected topic"}, headers={"X-CSRF-Token": csrf})
    post = await client.post("/api/v1/posts", json={"title": "Pending", "content": "content", "category_request_id": request.json()["id"]}, headers={"X-CSRF-Token": csrf})
    async with client._transport.app.state.session_factory() as session:
        admin = await session.scalar(select(User).where(User.username_normalized == "rejectcategory"))
        admin.role = "admin"
        await session.commit()
    rejected = await client.patch(f"/api/v1/admin/category-requests/{request.json()['id']}", json={"status": "rejected", "resolution": "Not a category"}, headers={"X-CSRF-Token": csrf})
    assert rejected.status_code == 200
    drafts = await client.get("/api/v1/drafts")
    assert drafts.json()["items"][0]["id"] == post.json()["id"]
    assert drafts.json()["items"][0]["status"] == "needs_category_change"
    assert drafts.json()["items"][0]["category_resolution"] == "Not a category"


@pytest.mark.asyncio
async def test_admin_category_requests_use_scoped_cursor(client: AsyncClient) -> None:
    csrf = await register(client, "categoryadmin")
    for name in ("Astronomy", "Biology", "Chemistry"):
        assert (await client.post("/api/v1/category-requests", json={"name": name}, headers={"X-CSRF-Token": csrf})).status_code == 201
    async with client._transport.app.state.session_factory() as session:
        admin = await session.scalar(select(User).where(User.username_normalized == "categoryadmin"))
        admin.role = "admin"
        await session.commit()
    first = await client.get("/api/v1/admin/category-requests", params={"limit": 2})
    assert first.status_code == 200
    assert len(first.json()["items"]) == 2
    assert first.json()["next_cursor"]
    second = await client.get("/api/v1/admin/category-requests", params={"limit": 2, "cursor": first.json()["next_cursor"]})
    assert len(second.json()["items"]) == 1
    assert (await client.get("/api/v1/admin/category-requests", params={"status": "approved", "cursor": first.json()["next_cursor"]})).status_code == 400
