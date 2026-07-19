import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_post_crud_filters_pagination_and_ownership(client: AsyncClient) -> None:
    csrf = await register(client, "alice")
    created = []
    for index in range(3):
        response = await client.post("/api/v1/posts", json={"title": f"Post {index}", "content": "content", "category": "tech", "tags": ["Python", "fastapi"]}, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 201
        created.append(response.json())

    feed = await client.get("/api/v1/posts", params={"tag": "PYTHON", "limit": 2})
    assert feed.status_code == 200
    assert len(feed.json()["items"]) == 2
    assert feed.json()["next_cursor"]
    next_page = await client.get("/api/v1/posts", params={"tag": "PYTHON", "cursor": feed.json()["next_cursor"], "limit": 2})
    assert len(next_page.json()["items"]) == 1

    post_id = created[0]["id"]
    updated = await client.patch(f"/api/v1/posts/{post_id}", json={"title": "Updated"}, headers={"X-CSRF-Token": csrf})
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated"
    assert (await client.delete(f"/api/v1/posts/{post_id}", headers={"X-CSRF-Token": csrf})).status_code == 204
    assert (await client.get(f"/api/v1/posts/{post_id}")).status_code == 404

    searched = await client.get("/api/v1/posts", params={"query": "Post", "search_in": "title", "sort": "oldest"})
    assert searched.status_code == 200
    assert [item["title"] for item in searched.json()["items"]] == ["Post 1", "Post 2"]

    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        other_csrf = await register(other, "bob")
        forbidden = await other.patch(f"/api/v1/posts/{created[1]['id']}", json={"title": "stolen"}, headers={"X-CSRF-Token": other_csrf})
        assert forbidden.status_code == 404
    finally:
        await other.aclose()
