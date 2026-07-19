import pytest
from httpx import AsyncClient


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
