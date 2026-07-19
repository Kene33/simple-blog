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
async def test_profile_fields_are_private_and_public_comments_are_paginated(client: AsyncClient) -> None:
    csrf = await register(client, "profileuser")
    profile = await client.patch("/api/v1/users/me", json={"display_name": "Profile User", "bio": "About me"}, headers={"X-CSRF-Token": csrf})
    assert profile.status_code == 200
    assert profile.json()["display_name"] == "Profile User"
    public = await client.get("/api/v1/users/profileuser")
    assert public.status_code == 200
    assert public.json()["display_name"] == "Profile User"
    assert "email" not in public.json()
    post_id = await create_post(client, csrf)
    comment = await client.post(f"/api/v1/posts/{post_id}/comments", json={"body": "Public reply"}, headers={"X-CSRF-Token": csrf})
    assert comment.status_code == 201
    comments = await client.get("/api/v1/users/profileuser/comments")
    assert comments.status_code == 200
    assert comments.json()["items"][0]["body"] == "Public reply"


@pytest.mark.asyncio
async def test_profile_cannot_attach_wrong_media_purpose_as_cover(client: AsyncClient) -> None:
    csrf = await register(client, "coveruser")
    post_media = await client.post("/api/v1/media", files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00", "image/png")}, data={"purpose": "post"}, headers={"X-CSRF-Token": csrf})
    assert post_media.status_code == 201
    response = await client.patch("/api/v1/users/me", json={"cover_media_id": post_media.json()["id"]}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 422
