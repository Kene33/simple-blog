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
    nested = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Nested", "parent_id": reply.json()["id"]}, headers={"X-CSRF-Token": csrf})
    assert nested.status_code == 201
    mismatched = await client.get(f"/api/v1/posts/{post_id}/comments", params={"parent_id": roots[0]["id"], "cursor": page.json()["next_cursor"]})
    assert mismatched.status_code == 400


@pytest.mark.asyncio
async def test_comment_branches_support_deep_nesting_and_cursors(client: AsyncClient) -> None:
    csrf = await register(client, "deepcommenter")
    post_id = await create_post(client, csrf)
    parent_id = None
    for depth in range(8):
        response = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": f"Depth {depth}", "parent_id": parent_id}, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 201
        parent_id = response.json()["id"]
    root = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Branch root"}, headers={"X-CSRF-Token": csrf})
    for index in range(3):
        assert (await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": f"Reply {index}", "parent_id": root.json()["id"]}, headers={"X-CSRF-Token": csrf})).status_code == 201
    first = await client.get(f"/api/v1/posts/{post_id}/comments", params={"parent_id": root.json()["id"], "limit": 2})
    assert len(first.json()["items"]) == 2
    second = await client.get(f"/api/v1/posts/{post_id}/comments", params={"parent_id": root.json()["id"], "limit": 2, "cursor": first.json()["next_cursor"]})
    assert len(second.json()["items"]) == 1


@pytest.mark.asyncio
async def test_comment_rejects_parent_from_another_post(client: AsyncClient) -> None:
    csrf = await register(client, "treeowner")
    first_post = await create_post(client, csrf)
    second_post = await client.post("/api/v1/posts", json={"title": "Second", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    root = await client.post(f"/api/v1/posts/{first_post}/comments", json={"body": "Root"}, headers={"X-CSRF-Token": csrf})
    invalid = await client.post(f"/api/v1/posts/{second_post.json()['id']}/comments", json={"body": "Wrong tree", "parent_id": root.json()["id"]}, headers={"X-CSRF-Token": csrf})
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_other_users_can_comment_and_read_comment(client: AsyncClient) -> None:
    owner_csrf = await register(client, "postowner")
    post_id = await create_post(client, owner_csrf)
    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        other_csrf = await register(other, "othercommenter")
        created = await other.post(f"/api/v1/posts/{post_id}/comments", json={"body": "From another user"}, headers={"X-CSRF-Token": other_csrf})
        assert created.status_code == 201
        read = await client.get(f"/api/v1/comments/{created.json()['id']}")
        assert read.status_code == 200
        assert read.json()["body"] == "From another user"
    finally:
        await other.aclose()


@pytest.mark.asyncio
async def test_guests_can_read_comments_but_cannot_change_them(client: AsyncClient) -> None:
    owner_csrf = await register(client, "guestreader")
    post_id = await create_post(client, owner_csrf)
    created = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Public comment"}, headers={"X-CSRF-Token": owner_csrf})
    comment_id = created.json()["id"]
    guest = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        visible = await guest.get(f"/api/v1/posts/{post_id}/comments")
        assert visible.status_code == 200
        assert visible.json()["items"][0]["body"] == "Public comment"
        assert (await guest.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Not allowed"})).status_code == 401
        assert (await guest.patch(f"/api/v1/comments/{comment_id}", json={"body": "Not allowed"})).status_code == 401
        assert (await guest.delete(f"/api/v1/comments/{comment_id}")).status_code == 401
    finally:
        await guest.aclose()


@pytest.mark.asyncio
async def test_comment_edit_delete_and_tombstone(client: AsyncClient) -> None:
    csrf = await register(client, "owner")
    post_id = await create_post(client, csrf)
    root = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Root"}, headers={"X-CSRF-Token": csrf})
    reply = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Reply", "parent_id": root.json()["id"]}, headers={"X-CSRF-Token": csrf})
    edited = await client.patch(f"/api/v1/comments/{reply.json()['id']}", json={"body": "Edited"}, headers={"X-CSRF-Token": csrf})
    assert edited.status_code == 200
    assert edited.json()["body"] == "Edited"
    deleted = await client.delete(f"/api/v1/comments/{root.json()['id']}", headers={"X-CSRF-Token": csrf})
    assert deleted.status_code == 204
    assert (await client.get(f"/api/v1/comments/{root.json()['id']}")).status_code == 404
    roots = await client.get(f"/api/v1/posts/{post_id}/comments")
    assert roots.json()["items"][0]["is_deleted"] is True
    assert roots.json()["items"][0]["body"] == "[deleted]"
    replies = await client.get(f"/api/v1/posts/{post_id}/comments", params={"parent_id": root.json()["id"]})
    assert replies.json()["items"][0]["id"] == reply.json()["id"]
    assert (await client.get(f"/api/v1/posts/{post_id}")).json()["comment_count"] == 1
    blocked = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Late", "parent_id": root.json()["id"]}, headers={"X-CSRF-Token": csrf})
    assert blocked.status_code == 422

    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        other_csrf = await register(other, "otherowner")
        assert (await other.patch(f"/api/v1/comments/{reply.json()['id']}", json={"body": "Stolen"}, headers={"X-CSRF-Token": other_csrf})).status_code == 404
    finally:
        await other.aclose()
