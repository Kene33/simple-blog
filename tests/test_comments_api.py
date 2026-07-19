import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


async def create_post(client: AsyncClient, csrf: str) -> str:
    response = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_comment_roots_replies_and_pagination(client: AsyncClient) -> None:
    csrf = await register(client, "commenter")
    post_id = await create_post(client, csrf)
    roots = []
    for body in ("One", "Two", "Three"):
        response = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": body}, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 201
        roots.append(response.json())
    reply = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Reply", "parent_id": roots[0]["id"]}, headers={"X-CSRF-Token": csrf})
    assert reply.status_code == 201
    assert reply.json()["parent_id"] == roots[0]["id"]

    page = await client.get(f"/api/v1/posts/{post_id}/comments", params={"limit": 2})
    assert page.status_code == 200
    assert len(page.json()["items"]) == 2
    assert page.json()["next_cursor"]
    next_page = await client.get(f"/api/v1/posts/{post_id}/comments", params={"limit": 2, "cursor": page.json()["next_cursor"]})
    assert len(next_page.json()["items"]) == 1
    replies = await client.get(f"/api/v1/posts/{post_id}/comments", params={"parent_id": roots[0]["id"]})
    assert [item["id"] for item in replies.json()["items"]] == [reply.json()["id"]]
    mismatched = await client.get(f"/api/v1/posts/{post_id}/comments", params={"parent_id": roots[0]["id"], "cursor": page.json()["next_cursor"]})
    assert mismatched.status_code == 400


@pytest.mark.asyncio
async def test_comment_rejects_parent_from_another_post(client: AsyncClient) -> None:
    csrf = await register(client, "treeowner")
    first_post = await create_post(client, csrf)
    second_post = await client.post("/api/v1/posts", json={"title": "Second", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    root = await client.post(f"/api/v1/posts/{first_post}/comments", json={"body": "Root"}, headers={"X-CSRF-Token": csrf})
    invalid = await client.post(f"/api/v1/posts/{second_post.json()['id']}/comments", json={"body": "Wrong tree", "parent_id": root.json()["id"]}, headers={"X-CSRF-Token": csrf})
    assert invalid.status_code == 422
