import pytest
from httpx import AsyncClient

import src.api.auth as auth_api


@pytest.mark.asyncio
async def test_auth_lifecycle_and_csrf(client: AsyncClient) -> None:
    register = await client.post("/api/v1/auth/register", json={"username": "Alice_1", "email": "Alice@example.com", "password": "strong-password"})
    assert register.status_code == 201
    assert "httponly" in register.headers["set-cookie"].lower()
    assert "access_token" not in register.json()

    csrf = client.cookies.get("csrf_token")
    assert csrf
    me = await client.get("/api/v1/users/me")
    assert me.status_code == 200
    assert me.json()["email"] == "Alice@example.com"

    rejected_update = await client.patch("/api/v1/users/me", json={"username": "alice_new"})
    assert rejected_update.status_code == 403
    updated = await client.patch("/api/v1/users/me", json={"username": "alice_new"}, headers={"X-CSRF-Token": csrf})
    assert updated.status_code == 200
    assert updated.json()["username"] == "alice_new"

    old_refresh = client.cookies.get("refresh_token")
    old_csrf = client.cookies.get("csrf_token")
    refreshed = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert refreshed.status_code == 200
    assert client.cookies.get("refresh_token") != old_refresh

    client.cookies.set("refresh_token", old_refresh)
    client.cookies.set("csrf_token", old_csrf)
    replay = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": old_csrf})
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "AUTH_INVALID"


@pytest.mark.asyncio
async def test_registration_rejects_short_username(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json={"username": "abcd", "email": "short@example.com", "password": "strong-password"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_email_verification_is_optional_until_confirmed(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, str] = {}

    async def fake_send(settings: object, recipient: str, token: str) -> None:
        sent[recipient] = token

    monkeypatch.setattr(auth_api, "send_email_verification", fake_send)
    response = await client.post("/api/v1/auth/register", json={"username": "verifyuser", "email": "verify@example.com", "password": "strong-password"})
    assert response.status_code == 201
    assert response.json()["user"]["email_verified"] is False

    verified = await client.get(f"/api/v1/auth/verify-email?token={sent['verify@example.com']}")
    assert verified.status_code == 200
    assert (await client.get("/api/v1/users/me")).json()["email_verified"] is True
    repeated = await client.get(f"/api/v1/auth/verify-email?token={sent['verify@example.com']}")
    assert repeated.status_code == 200
    assert repeated.json()["message"] == "Email already verified"


@pytest.mark.asyncio
async def test_email_verification_link_can_use_path_token(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, str] = {}

    async def fake_send(settings: object, recipient: str, token: str) -> None:
        sent[recipient] = token

    monkeypatch.setattr(auth_api, "send_email_verification", fake_send)
    response = await client.post("/api/v1/auth/register", json={"username": "pathverify", "email": "pathverify@example.com", "password": "strong-password"})
    assert response.status_code == 201
    verified = await client.get(f"/api/v1/auth/verify-email/{sent['pathverify@example.com']}")
    assert verified.status_code == 200


@pytest.mark.asyncio
async def test_duplicate_identity_and_profile_privacy(client: AsyncClient) -> None:
    payload = {"username": "alice", "email": "alice@example.com", "password": "strong-password"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    duplicate = await client.post("/api/v1/auth/register", json={**payload, "email": "ALICE@example.com"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "RESOURCE_CONFLICT"

    public = await client.get("/api/v1/users/ALICE")
    assert public.status_code == 200
    assert "email" not in public.json()
    assert "role" not in public.json()


@pytest.mark.asyncio
async def test_missing_refresh_csrf_and_logout(client: AsyncClient) -> None:
    missing_refresh = await client.post("/api/v1/auth/refresh")
    assert missing_refresh.status_code == 401
    assert missing_refresh.json()["error"]["code"] == "AUTH_REQUIRED"

    payload = {"username": "alice", "email": "alice@example.com", "password": "strong-password"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    invalid_csrf = await client.post("/api/v1/auth/refresh", headers={"X-CSRF-Token": "wrong"})
    assert invalid_csrf.status_code == 403
    assert invalid_csrf.json()["error"]["code"] == "CSRF_FAILED"

    csrf = client.cookies.get("csrf_token")
    logout = await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf})
    assert logout.status_code == 204
    assert (await client.get("/api/v1/users/me")).status_code == 401


@pytest.mark.asyncio
async def test_password_reset_is_single_use_and_revokes_sessions(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, str] = {}

    async def fake_send(settings: object, recipient: str, token: str) -> None:
        sent[recipient] = token

    monkeypatch.setattr("src.api.auth.send_password_reset_email", fake_send)
    payload = {"username": "resetuser", "email": "reset@example.com", "password": "strong-password"}
    assert (await client.post("/api/v1/auth/register", json=payload)).status_code == 201
    requested = await client.post("/api/v1/auth/password-reset/request", json={"email": payload["email"]})
    assert requested.status_code == 200
    assert requested.json()["message"]
    assert "reset_token" not in requested.json()
    token = sent[payload["email"]]
    assert (await client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "password": "new-strong-password"})).status_code == 204
    assert (await client.post("/api/v1/auth/password-reset/confirm", json={"token": token, "password": "another-password"})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"identifier": payload["email"], "password": payload["password"]})).status_code == 401
    assert (await client.post("/api/v1/auth/login", json={"identifier": payload["email"], "password": "new-strong-password"})).status_code == 200


@pytest.mark.asyncio
async def test_public_feed_ignores_invalid_optional_auth_cookie(client: AsyncClient) -> None:
    client.cookies.set("access_token", "broken", domain="testserver", path="/")
    response = await client.get("/api/v1/posts")
    assert response.status_code == 200
