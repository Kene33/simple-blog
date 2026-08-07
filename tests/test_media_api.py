import base64

import pytest
from httpx import AsyncClient

from tests.conftest import FakeStorage

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


async def register(client: AsyncClient) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": "mediauser", "email": "mediauser@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_upload_and_delete_unattached_image(client: AsyncClient, storage: FakeStorage) -> None:
    csrf = await register(client)
    response = await client.post("/api/v1/media", data={"purpose": "post"}, files={"file": ("photo.png", PNG, "image/png")}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 201
    media = response.json()
    assert media["kind"] == "image"
    assert media["status"] == "uploaded"
    assert len(storage.objects) == 1

    deleted = await client.delete(f"/api/v1/media/{media['id']}", headers={"X-CSRF-Token": csrf})
    assert deleted.status_code == 204
    assert not storage.objects


@pytest.mark.asyncio
async def test_upload_rejects_invalid_type_and_avatar_video(client: AsyncClient) -> None:
    csrf = await register(client)
    invalid = await client.post("/api/v1/media", data={"purpose": "post"}, files={"file": ("bad.txt", b"not an image", "text/plain")}, headers={"X-CSRF-Token": csrf})
    assert invalid.status_code == 415
    assert invalid.json()["error"]["code"] == "MEDIA_UNSUPPORTED"

    video = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64
    avatar = await client.post("/api/v1/media", data={"purpose": "avatar"}, files={"file": ("movie.mp4", video, "video/mp4")}, headers={"X-CSRF-Token": csrf})
    assert avatar.status_code == 415


@pytest.mark.asyncio
async def test_avatar_requires_avatar_upload(client: AsyncClient) -> None:
    csrf = await register(client)
    post_media = await client.post("/api/v1/media", data={"purpose": "post"}, files={"file": ("photo.png", PNG, "image/png")}, headers={"X-CSRF-Token": csrf})
    assert post_media.status_code == 201
    rejected = await client.patch("/api/v1/users/me", json={"avatar_media_id": post_media.json()["id"]}, headers={"X-CSRF-Token": csrf})
    assert rejected.status_code == 422

    avatar_media = await client.post("/api/v1/media", data={"purpose": "avatar"}, files={"file": ("avatar.png", PNG, "image/png")}, headers={"X-CSRF-Token": csrf})
    assert avatar_media.status_code == 201
    updated = await client.patch("/api/v1/users/me", json={"avatar_media_id": avatar_media.json()["id"]}, headers={"X-CSRF-Token": csrf})
    assert updated.status_code == 200
    assert updated.json()["avatar_url"] == avatar_media.json()["url"]
    assert (await client.get(avatar_media.json()["url"])).status_code == 200
    anonymous = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        assert (await anonymous.get(avatar_media.json()["url"])).status_code == 200
    finally:
        await anonymous.aclose()


@pytest.mark.asyncio
async def test_post_accepts_only_owned_post_uploads(client: AsyncClient) -> None:
    csrf = await register(client)
    upload = await client.post("/api/v1/media", data={"purpose": "post"}, files={"file": ("photo.png", PNG, "image/png")}, headers={"X-CSRF-Token": csrf})
    assert upload.status_code == 201
    media_id = upload.json()["id"]
    post = await client.post("/api/v1/posts", json={"title": "With image", "content": "content", "category": "tech", "media_ids": [media_id]}, headers={"X-CSRF-Token": csrf})
    assert post.status_code == 201
    assert post.json()["media"][0]["id"] == media_id
    assert (await client.delete(f"/api/v1/media/{media_id}", headers={"X-CSRF-Token": csrf})).status_code == 409


@pytest.mark.asyncio
async def test_public_media_uses_revocable_cache_ttl(client: AsyncClient) -> None:
    csrf = await register(client)
    upload = await client.post("/api/v1/media", data={"purpose": "post"}, files={"file": ("photo.png", PNG, "image/png")}, headers={"X-CSRF-Token": csrf})
    assert upload.status_code == 201
    post = await client.post("/api/v1/posts", json={"title": "Public", "content": "content", "category": "tech", "media_ids": [upload.json()["id"]]}, headers={"X-CSRF-Token": csrf})
    assert post.status_code == 201

    anonymous = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        response = await anonymous.get(upload.json()["url"])
    finally:
        await anonymous.aclose()

    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=300, stale-while-revalidate=60"


@pytest.mark.asyncio
async def test_uploaded_media_is_private(client: AsyncClient) -> None:
    csrf = await register(client)
    upload = await client.post("/api/v1/media", data={"purpose": "post"}, files={"file": ("photo.png", PNG, "image/png")}, headers={"X-CSRF-Token": csrf})
    assert upload.status_code == 201
    anonymous = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        assert (await anonymous.get(upload.json()["url"])).status_code == 404
    finally:
        await anonymous.aclose()
