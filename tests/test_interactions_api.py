import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_likes_are_idempotent_and_visible_to_current_user(client: AsyncClient) -> None:
    csrf = await register(client, "liker")
    post = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    post_id = post.json()["id"]
    first = await client.put(f"/api/v1/posts/{post_id}/like", headers={"X-CSRF-Token": csrf})
    second = await client.put(f"/api/v1/posts/{post_id}/like", headers={"X-CSRF-Token": csrf})
    assert first.json() == second.json() == {"post_id": post_id, "like_count": 1, "liked_by_me": True}
    assert (await client.get(f"/api/v1/posts/{post_id}")).json()["liked_by_me"] is True

    anonymous = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        assert (await anonymous.get(f"/api/v1/posts/{post_id}")).json()["liked_by_me"] is False
    finally:
        await anonymous.aclose()
    assert (await client.delete(f"/api/v1/posts/{post_id}/like", headers={"X-CSRF-Token": csrf})).status_code == 204
    assert (await client.delete(f"/api/v1/posts/{post_id}/like", headers={"X-CSRF-Token": csrf})).status_code == 204
    assert (await client.get(f"/api/v1/posts/{post_id}")).json()["like_count"] == 0


@pytest.mark.asyncio
async def test_other_users_can_like_a_public_post(client: AsyncClient) -> None:
    owner_csrf = await register(client, "likeowner")
    post = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": owner_csrf})
    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        other_csrf = await register(other, "otherliker")
        liked = await other.put(f"/api/v1/posts/{post.json()['id']}/like", headers={"X-CSRF-Token": other_csrf})
        assert liked.status_code == 200
        assert liked.json()["like_count"] == 1
    finally:
        await other.aclose()


@pytest.mark.asyncio
async def test_shares_support_anonymous_and_authenticated_events(client: AsyncClient) -> None:
    csrf = await register(client, "sharer")
    post = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    post_id = post.json()["id"]
    anonymous = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        copied = await anonymous.post(f"/api/v1/posts/{post_id}/shares", json={"channel": "copy"})
        assert copied.status_code == 201
    finally:
        await anonymous.aclose()
    native = await client.post(f"/api/v1/posts/{post_id}/shares", json={"channel": "native"}, headers={"X-CSRF-Token": csrf})
    assert native.status_code == 201
    assert native.json()["share_count"] == 2
    assert native.json()["canonical_url"].endswith(f"/posts/{post_id}")
    assert (await client.post(f"/api/v1/posts/{post_id}/shares", json={"channel": "copy"})).status_code == 403


@pytest.mark.asyncio
async def test_authenticated_copy_share_counts_once_per_account(client: AsyncClient) -> None:
    csrf = await register(client, "copysharer")
    post = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    post_id = post.json()["id"]
    for expected_count in (1, 1):
        response = await client.post(f"/api/v1/posts/{post_id}/shares", json={"channel": "copy"}, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 201
        assert response.json()["share_count"] == expected_count
