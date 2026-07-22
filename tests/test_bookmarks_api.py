import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


async def create_post(client: AsyncClient, csrf: str, title: str) -> str:
    response = await client.post("/api/v1/posts", json={"title": title, "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_bookmark_is_idempotent_and_in_post_read(client: AsyncClient) -> None:
    csrf = await register(client, "bookmarkuser")
    post_id = await create_post(client, csrf, "Bookmarked")
    first = await client.put(f"/api/v1/posts/{post_id}/bookmark", headers={"X-CSRF-Token": csrf})
    second = await client.put(f"/api/v1/posts/{post_id}/bookmark", headers={"X-CSRF-Token": csrf})
    assert first.status_code == second.status_code == 200
    assert (await client.get(f"/api/v1/posts/{post_id}")).json()["bookmarked_by_me"] is True
    saved = await client.get("/api/v1/bookmarks")
    assert [item["id"] for item in saved.json()["items"]] == [post_id]
    assert (await client.delete(f"/api/v1/posts/{post_id}/bookmark", headers={"X-CSRF-Token": csrf})).status_code == 204
    assert (await client.get(f"/api/v1/posts/{post_id}")).json()["bookmarked_by_me"] is False


@pytest.mark.asyncio
async def test_other_users_can_bookmark_a_public_post(client: AsyncClient) -> None:
    owner_csrf = await register(client, "bookmarkowner")
    post_id = await create_post(client, owner_csrf, "Public post")
    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        other_csrf = await register(other, "otherbookmarker")
        bookmarked = await other.put(f"/api/v1/posts/{post_id}/bookmark", headers={"X-CSRF-Token": other_csrf})
        assert bookmarked.status_code == 200
        assert (await other.get("/api/v1/bookmarks")).json()["items"][0]["id"] == post_id
    finally:
        await other.aclose()


@pytest.mark.asyncio
async def test_bookmarks_are_private_and_paginated(client: AsyncClient) -> None:
    csrf = await register(client, "bookmarklist")
    post_ids = [await create_post(client, csrf, f"Post {index}") for index in range(3)]
    for post_id in post_ids:
        assert (await client.put(f"/api/v1/posts/{post_id}/bookmark", headers={"X-CSRF-Token": csrf})).status_code == 200
    page = await client.get("/api/v1/bookmarks", params={"limit": 2})
    assert len(page.json()["items"]) == 2
    assert page.json()["next_cursor"]
    next_page = await client.get("/api/v1/bookmarks", params={"cursor": page.json()["next_cursor"], "limit": 2})
    assert len(next_page.json()["items"]) == 1

    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        await register(other, "bookmarkother")
        assert (await other.get("/api/v1/bookmarks")).json()["items"] == []
    finally:
        await other.aclose()
