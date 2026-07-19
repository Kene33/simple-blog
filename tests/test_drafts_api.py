import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_draft_crud_publish_and_isolation(client: AsyncClient) -> None:
    csrf = await register(client, "draftowner")
    created = await client.post("/api/v1/drafts", json={"title": "", "content": "unfinished"}, headers={"X-CSRF-Token": csrf})
    assert created.status_code == 201
    draft = created.json()
    assert draft["status"] == "draft"
    assert (await client.get("/api/v1/posts")).json()["items"] == []

    updated = await client.patch(f"/api/v1/drafts/{draft['id']}", json={"title": "Ready", "category": "tech", "tags": ["Python"]}, headers={"X-CSRF-Token": csrf})
    assert updated.status_code == 200
    assert updated.json()["tags"] == ["python"]
    published = await client.post(f"/api/v1/drafts/{draft['id']}/publish", headers={"X-CSRF-Token": csrf})
    assert published.status_code == 200
    assert published.json()["title"] == "Ready"
    assert (await client.get(f"/api/v1/drafts/{draft['id']}", headers={"X-CSRF-Token": csrf})).status_code == 404
    assert (await client.get(f"/api/v1/posts/{draft['id']}")).status_code == 200


@pytest.mark.asyncio
async def test_draft_requires_required_fields_to_publish(client: AsyncClient) -> None:
    csrf = await register(client, "incomplete")
    draft = await client.post("/api/v1/drafts", json={"title": "Only title"}, headers={"X-CSRF-Token": csrf})
    response = await client.post(f"/api/v1/drafts/{draft.json()['id']}/publish", headers={"X-CSRF-Token": csrf})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_draft_list_is_private_and_cursor_paginated(client: AsyncClient) -> None:
    csrf = await register(client, "draftlist")
    for index in range(3):
        response = await client.post("/api/v1/drafts", json={"title": f"Draft {index}"}, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 201
    page = await client.get("/api/v1/drafts", params={"limit": 2}, headers={"X-CSRF-Token": csrf})
    assert page.status_code == 200
    assert len(page.json()["items"]) == 2
    assert page.json()["next_cursor"]
    next_page = await client.get("/api/v1/drafts", params={"cursor": page.json()["next_cursor"], "limit": 2}, headers={"X-CSRF-Token": csrf})
    assert len(next_page.json()["items"]) == 1
