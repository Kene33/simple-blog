import base64

import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_user_can_change_username_and_password(client: AsyncClient) -> None:
    csrf = await register(client, "renameuser")
    changed = await client.patch("/api/v1/users/me", json={"username": "renameduser", "current_password": "strong-password", "new_password": "new-strong-password"}, headers={"X-CSRF-Token": csrf})
    assert changed.status_code == 200
    assert changed.json()["username"] == "renameduser"
    assert (await client.post("/api/v1/auth/login", json={"identifier": "renameduser", "password": "strong-password"})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"identifier": "renameduser", "password": "new-strong-password"})).status_code == 200


@pytest.mark.asyncio
async def test_username_change_rejects_taken_username(client: AsyncClient) -> None:
    await register(client, "takenname")
    second = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        csrf = await register(second, "othername")
        response = await second.patch("/api/v1/users/me", json={"username": "takenname"}, headers={"X-CSRF-Token": csrf})
        assert response.status_code == 409
    finally:
        await second.aclose()


async def create_post(client: AsyncClient, csrf: str) -> str:
    response = await client.post("/api/v1/posts", json={"title": "Post", "content": "content", "category": "tech"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.asyncio
async def test_profile_fields_are_private_and_public_comments_are_paginated(client: AsyncClient) -> None:
    csrf = await register(client, "profileuser")
    profile = await client.patch("/api/v1/users/me", json={"display_name": "Profile User", "bio": "About me"}, headers={"X-CSRF-Token": csrf})
    assert profile.status_code == 200
    assert profile.json()["display_name"] == "Profile User"
    public = await client.get("/api/v1/users/profileuser")
    assert public.status_code == 200
    assert public.json()["display_name"] == "Profile User"
    assert "email" not in public.json()
    cleared = await client.patch("/api/v1/users/me", json={"display_name": None, "bio": None}, headers={"X-CSRF-Token": csrf})
    assert cleared.status_code == 200
    assert cleared.json()["display_name"] is None
    post_id = await create_post(client, csrf)
    comment = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Public reply"}, headers={"X-CSRF-Token": csrf})
    assert comment.status_code == 201
    comments = await client.get("/api/v1/users/profileuser/comments")
    assert comments.status_code == 200
    assert comments.json()["items"][0]["body"] == "Public reply"


@pytest.mark.asyncio
async def test_profile_cannot_attach_wrong_media_purpose_as_cover(client: AsyncClient) -> None:
    csrf = await register(client, "coveruser")
    post_media = await client.post("/api/v1/media", files={"file": ("photo.png", base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="), "image/png")}, data={"purpose": "post"}, headers={"X-CSRF-Token": csrf})
    assert post_media.status_code == 201
    response = await client.patch("/api/v1/users/me", json={"cover_media_id": post_media.json()["id"]}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_profile_post_and_comment_visibility(client: AsyncClient) -> None:
    csrf = await register(client, "privateuser")
    post_id = await create_post(client, csrf)
    comment = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Hidden reply"}, headers={"X-CSRF-Token": csrf})
    assert comment.status_code == 201
    private_posts = await client.patch("/api/v1/users/me", json={"posts_visibility": "private", "comments_visibility": "private"}, headers={"X-CSRF-Token": csrf})
    assert private_posts.status_code == 200
    assert private_posts.json()["posts_visibility"] == "private"
    assert (await client.get("/api/v1/posts", params={"author": "privateuser"})).json()["items"]
    assert (await client.get(f"/api/v1/posts/{post_id}/comments")).status_code == 200
    assert (await client.get(f"/api/v1/comments/{comment.json()['id']}")).status_code == 200

    guest = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        assert (await guest.get("/api/v1/posts", params={"author": "privateuser"})).json()["items"] == []
        assert (await guest.get("/api/v1/users/privateuser/comments")).json()["items"] == []
        hidden_profile = await client.patch("/api/v1/users/me", json={"profile_visibility": "private"}, headers={"X-CSRF-Token": csrf})
        assert hidden_profile.status_code == 200
        assert (await guest.get("/api/v1/users/privateuser")).status_code == 404
    finally:
        await guest.aclose()
