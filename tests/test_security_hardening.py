import base64

import pytest
from httpx import AsyncClient


async def register(client: AsyncClient, username: str) -> str:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token")


@pytest.mark.asyncio
async def test_security_headers_cors_and_health_contract(client: AsyncClient) -> None:
    live = await client.get("/health/live")
    assert live.status_code == 200
    assert live.json() == {"status": "ok"}
    assert live.headers["content-security-policy"]
    assert live.headers["referrer-policy"] == "no-referrer"
    assert live.headers["permissions-policy"]
    assert live.headers["x-frame-options"] == "DENY"
    assert (await client.get("/robots.txt")).text.startswith("User-agent")
    hostile = await client.options("/api/v1/posts", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in hostile.headers


@pytest.mark.asyncio
async def test_registration_rate_limit_is_enforced(client: AsyncClient) -> None:
    for index in range(5):
        assert (await client.post("/api/v1/auth/register", json={"username": f"limit{index}", "email": f"limit{index}@example.com", "password": "strong-password"})).status_code == 201
    blocked = await client.post("/api/v1/auth/register", json={"username": "limit5", "email": "limit5@example.com", "password": "strong-password"})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.asyncio
async def test_password_reset_rate_limit_has_ip_and_email_buckets(client: AsyncClient) -> None:
    for _ in range(5):
        response = await client.post("/api/v1/auth/password-reset/request", json={"email": "user@example.com"})
        assert response.status_code == 200
    blocked_email = await client.post("/api/v1/auth/password-reset/request", json={"email": "user@example.com"})
    assert blocked_email.status_code == 429
    for index in range(14):
        response = await client.post("/api/v1/auth/password-reset/request", json={"email": f"user-{index}@example.com"})
        assert response.status_code == 200
    blocked_ip = await client.post("/api/v1/auth/password-reset/request", json={"email": "last@example.com"})
    assert blocked_ip.status_code == 429


@pytest.mark.asyncio
async def test_attached_media_from_private_post_is_not_public(client: AsyncClient) -> None:
    csrf = await register(client, "private_media")
    image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
    upload = await client.post("/api/v1/media", data={"purpose": "post"}, files={"file": ("photo.png", image, "image/png")}, headers={"X-CSRF-Token": csrf})
    assert upload.status_code == 201
    post = await client.post("/api/v1/posts", json={"title": "Private", "content": "text", "category": "tech", "media_ids": [upload.json()["id"]]}, headers={"X-CSRF-Token": csrf})
    assert post.status_code == 201
    assert (await client.patch("/api/v1/users/me", json={"posts_visibility": "private"}, headers={"X-CSRF-Token": csrf})).status_code == 200
    anonymous = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        assert (await anonymous.get(upload.json()["url"])).status_code == 404
    finally:
        await anonymous.aclose()
