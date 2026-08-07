import base64

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import User


async def register(client: AsyncClient, username: str) -> tuple[str, str]:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    csrf = client.cookies.get("csrf_token")
    device = await client.post("/api/v1/messaging/devices", json={"public_key": {"kty": "EC", "crv": "P-256", "x": username, "y": "key"}, "label": "Test"}, headers={"X-CSRF-Token": csrf})
    assert device.status_code == 201
    return csrf, response.json()["user"]["id"]


async def encrypted_payload(client: AsyncClient, text: str, **extra: object) -> dict[str, object]:
    device = (await client.get("/api/v1/messaging/devices")).json()["items"][0]
    return {"envelope": {"version": 1, "sender_device_id": device["id"], "recipients": [{"device_id": device["id"], "iv": "a", "ciphertext": text}]}, **extra}


@pytest.mark.asyncio
async def test_direct_messages_are_isolated_to_conversation_members(client: AsyncClient) -> None:
    owner_csrf, owner_id = await register(client, "messageowner")
    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    outsider = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        other_csrf, other_id = await register(other, "messagereader")
        conversation = await client.post(f"/api/v1/conversations/direct/{other_id}", headers={"X-CSRF-Token": owner_csrf})
        assert conversation.status_code in {200, 201}
        conversation_id = conversation.json()["id"]
        message = await client.post(f"/api/v1/conversations/{conversation_id}/messages", json=await encrypted_payload(client, "Hello"), headers={"X-CSRF-Token": owner_csrf})
        assert message.status_code == 201
        message_id = message.json()["id"]
        assert message.json()["sender"]["id"] == owner_id
        second_message = await client.post(f"/api/v1/conversations/{conversation_id}/messages", json=await encrypted_payload(client, "Second"), headers={"X-CSRF-Token": owner_csrf})
        assert second_message.status_code == 201

        assert (await other.get("/api/v1/conversations")).json()["items"][0]["id"] == conversation_id
        history = await other.get(f"/api/v1/conversations/{conversation_id}/messages", params={"limit": 1})
        assert history.status_code == 200
        assert history.json()["items"][0]["envelope"]["version"] == 1
        next_history = await other.get(f"/api/v1/conversations/{conversation_id}/messages", params={"limit": 1, "cursor": history.json()["next_cursor"]})
        assert next_history.json()["items"][0]["envelope"]["version"] == 1
        search = await other.get(f"/api/v1/conversations/{conversation_id}/messages/search", params={"q": "hello"})
        assert search.status_code == 409
        assert (await client.post(f"/api/v1/users/{other_id}/block", headers={"X-CSRF-Token": owner_csrf})).status_code == 204
        blocked_send = await client.post(f"/api/v1/conversations/{conversation_id}/messages", json=await encrypted_payload(client, "blocked"), headers={"X-CSRF-Token": owner_csrf})
        assert blocked_send.status_code == 404
        assert (await client.delete(f"/api/v1/users/{other_id}/block", headers={"X-CSRF-Token": owner_csrf})).status_code == 204
        assert (await other.patch(f"/api/v1/messages/{message_id}", json=await encrypted_payload(other, "stolen"), headers={"X-CSRF-Token": other_csrf})).status_code == 404
        assert (await other.patch(f"/api/v1/conversations/{conversation_id}/read", json={"message_id": message_id}, headers={"X-CSRF-Token": other_csrf})).status_code == 204

        outsider_csrf, _ = await register(outsider, "messageoutsider")
        assert (await outsider.get(f"/api/v1/conversations/{conversation_id}/messages")).status_code == 404
        assert (await outsider.post(f"/api/v1/conversations/{conversation_id}/messages", json=await encrypted_payload(outsider, "intrusion"), headers={"X-CSRF-Token": outsider_csrf})).status_code == 404
    finally:
        await other.aclose()
        await outsider.aclose()


@pytest.mark.asyncio
async def test_devices_are_registered_and_scoped_to_conversation_members(client: AsyncClient) -> None:
    owner_csrf, owner_id = await register(client, "deviceowner")
    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    outsider = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        other_csrf, other_id = await register(other, "devicereader")
        _, _ = await register(outsider, "deviceoutsider")
        owner_device = (await client.get("/api/v1/messaging/devices")).json()["items"][0]
        conversation = await client.post(f"/api/v1/conversations/direct/{other_id}", headers={"X-CSRF-Token": owner_csrf})
        conversation_id = conversation.json()["id"]
        other_device = (await other.get("/api/v1/messaging/devices")).json()["items"][0]
        devices = await client.get(f"/api/v1/conversations/{conversation_id}/devices")
        assert devices.status_code == 200
        assert {owner_device["id"], other_device["id"]} <= {item["id"] for item in devices.json()["items"]}
        assert (await outsider.get(f"/api/v1/conversations/{conversation_id}/devices")).status_code == 404
        assert (await client.delete(f"/api/v1/messaging/devices/{owner_device['id']}", headers={"X-CSRF-Token": owner_csrf})).status_code == 204
        assert (await client.get("/api/v1/messaging/devices")).json()["items"] == []
    finally:
        await other.aclose()
        await outsider.aclose()


@pytest.mark.asyncio
async def test_messages_accept_only_encrypted_envelopes(client: AsyncClient) -> None:
    owner_csrf, _ = await register(client, "envelopeowner")
    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        _, other_id = await register(other, "envelopereader")
        conversation = await client.post(f"/api/v1/conversations/direct/{other_id}", headers={"X-CSRF-Token": owner_csrf})
        device = await client.post("/api/v1/messaging/devices", json={"public_key": {"kty": "EC", "crv": "P-256", "x": "owner", "y": "key"}, "label": "Test"}, headers={"X-CSRF-Token": owner_csrf})
        payload = {"envelope": {"version": 1, "sender_device_id": device.json()["id"], "recipients": [{"device_id": "00000000-0000-0000-0000-000000000002", "iv": "a", "ciphertext": "b"}]}}
        sent = await client.post(f"/api/v1/conversations/{conversation.json()['id']}/messages", json=payload, headers={"X-CSRF-Token": owner_csrf})
        assert sent.status_code == 201
        assert sent.json()["envelope"] == payload["envelope"]
        assert "body" not in sent.json()
        assert (await other.get(f"/api/v1/conversations/{conversation.json()['id']}/messages/search", params={"q": "secret"})).status_code == 409
    finally:
        await other.aclose()


@pytest.mark.asyncio
async def test_message_media_is_owned_and_private_to_conversation_members(client: AsyncClient) -> None:
    owner_csrf, _ = await register(client, "attachmentowner")
    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    outsider = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        _, other_id = await register(other, "attachmentreader")
        _, _ = await register(outsider, "attachmentoutsider")
        conversation = await client.post(f"/api/v1/conversations/direct/{other_id}", headers={"X-CSRF-Token": owner_csrf})
        image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")
        upload = await client.post("/api/v1/media", data={"purpose": "message"}, files={"file": ("photo.png", image, "image/png")}, headers={"X-CSRF-Token": owner_csrf})
        assert upload.status_code == 201
        sent = await client.post(f"/api/v1/conversations/{conversation.json()['id']}/messages", json=await encrypted_payload(client, "Photo", media_ids=[upload.json()["id"]]), headers={"X-CSRF-Token": owner_csrf})
        assert sent.status_code == 201
        assert sent.json()["media"][0]["id"] == upload.json()["id"]
        assert (await other.get(upload.json()["url"])).status_code == 200
        assert (await outsider.get(upload.json()["url"])).status_code == 404
    finally:
        await other.aclose()
        await outsider.aclose()


@pytest.mark.asyncio
async def test_conversation_mute_and_block_state_are_scoped_to_member(client: AsyncClient) -> None:
    owner_csrf, _ = await register(client, "stateowner")
    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        _, other_id = await register(other, "statereader")
        conversation = await client.post(f"/api/v1/conversations/direct/{other_id}", headers={"X-CSRF-Token": owner_csrf})
        conversation_id = conversation.json()["id"]
        assert conversation.json()["muted"] is False
        assert conversation.json()["blocked"] is False

        muted = await client.post(f"/api/v1/conversations/{conversation_id}/mute", json={"muted": True}, headers={"X-CSRF-Token": owner_csrf})
        assert muted.status_code == 200
        assert muted.json()["muted"] is True
        owner_list = await client.get("/api/v1/conversations")
        assert owner_list.json()["items"][0]["muted"] is True
        assert (await other.get("/api/v1/conversations")).json()["items"][0]["muted"] is False

        assert (await client.post(f"/api/v1/users/{other_id}/block", headers={"X-CSRF-Token": owner_csrf})).status_code == 204
        blocked_list = await client.get("/api/v1/conversations")
        assert blocked_list.json()["items"][0]["blocked"] is True
        assert (await other.get("/api/v1/conversations")).json()["items"][0]["blocked"] is True
    finally:
        await other.aclose()


@pytest.mark.asyncio
async def test_group_messages_are_delivered_to_all_members(client: AsyncClient) -> None:
    owner_csrf, owner_id = await register(client, "groupowner")
    first = AsyncClient(transport=client._transport, base_url="http://testserver")
    second = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        _, first_id = await register(first, "groupfirst")
        _, second_id = await register(second, "groupsecond")
        conversation = await client.post("/api/v1/conversations/groups", json={"title": "Team", "member_ids": [first_id, second_id]}, headers={"X-CSRF-Token": owner_csrf})
        assert conversation.status_code == 201
        assert conversation.json()["kind"] == "group"
        assert len(conversation.json()["participants"]) == 2
        message = await client.post(f"/api/v1/conversations/{conversation.json()['id']}/messages", json=await encrypted_payload(client, "Hello team"), headers={"X-CSRF-Token": owner_csrf})
        assert message.status_code == 201
        assert (await first.get(f"/api/v1/conversations/{conversation.json()['id']}/messages")).json()["items"][0]["envelope"]["version"] == 1
        assert (await second.get(f"/api/v1/conversations/{conversation.json()['id']}/messages")).json()["items"][0]["sender"]["id"] == owner_id
    finally:
        await first.aclose()
        await second.aclose()


@pytest.mark.asyncio
async def test_group_admin_can_add_and_remove_members(client: AsyncClient) -> None:
    owner_csrf, _ = await register(client, "groupadmin")
    first = AsyncClient(transport=client._transport, base_url="http://testserver")
    second = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        _, first_id = await register(first, "groupmemberone")
        _, second_id = await register(second, "groupmembertwo")
        conversation = await client.post("/api/v1/conversations/groups", json={"title": "Team", "member_ids": [first_id]}, headers={"X-CSRF-Token": owner_csrf})
        conversation_id = conversation.json()["id"]
        added = await client.post(f"/api/v1/conversations/{conversation_id}/members", json={"user_id": second_id}, headers={"X-CSRF-Token": owner_csrf})
        assert added.status_code == 204
        assert len((await second.get(f"/api/v1/conversations/{conversation_id}/messages")).json()["items"]) == 0
        removed = await client.delete(f"/api/v1/conversations/{conversation_id}/members/{second_id}", headers={"X-CSRF-Token": owner_csrf})
        assert removed.status_code == 204
        assert (await second.get(f"/api/v1/conversations/{conversation_id}/messages")).status_code == 404
    finally:
        await first.aclose()
        await second.aclose()


@pytest.mark.asyncio
async def test_push_subscription_is_scoped_to_authenticated_user(client: AsyncClient) -> None:
    csrf, _ = await register(client, "pushowner")
    payload = {"endpoint": "https://push.example/subscription", "p256dh": "p256dh-key-value", "auth": "auth-key-value"}
    assert (await client.post("/api/v1/push/subscriptions", json=payload, headers={"X-CSRF-Token": csrf})).status_code == 204
    assert (await client.request("DELETE", "/api/v1/push/subscriptions", json=payload, headers={"X-CSRF-Token": csrf})).status_code == 204


@pytest.mark.asyncio
async def test_message_events_are_published_for_mutations(client: AsyncClient) -> None:
    owner_csrf, _ = await register(client, "eventowner")
    other = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        _, other_id = await register(other, "eventreader")
        bridge = client._transport.app.state.realtime_bridge
        events: list[tuple[str, str, dict[str, object]]] = []

        async def publish(user_id: object, event: dict[str, object]) -> None:
            events.append((str(user_id), str(event["type"]), event))

        bridge.publish = publish
        conversation = await client.post(f"/api/v1/conversations/direct/{other_id}", headers={"X-CSRF-Token": owner_csrf})
        conversation_id = conversation.json()["id"]
        message = await client.post(f"/api/v1/conversations/{conversation_id}/messages", json=await encrypted_payload(client, "Hello"), headers={"X-CSRF-Token": owner_csrf})
        message_id = message.json()["id"]
        await client.patch(f"/api/v1/messages/{message_id}", json=await encrypted_payload(client, "Edited"), headers={"X-CSRF-Token": owner_csrf})
        await client.delete(f"/api/v1/messages/{message_id}", headers={"X-CSRF-Token": owner_csrf})
        await other.patch(f"/api/v1/conversations/{conversation_id}/read", json={"message_id": message_id}, headers={"X-CSRF-Token": other.cookies.get("csrf_token")})
        assert [event[1] for event in events] == ["message.created", "message.updated", "message.deleted", "message.read"]
        assert events[0][2]["message"]["id"] == message_id
        assert events[1][2]["message"]["envelope"]["version"] == 1
        assert events[2][2]["message_id"] == message_id
        assert events[3][2]["message_id"] == message_id
    finally:
        await other.aclose()


@pytest.mark.asyncio
async def test_message_can_be_reported_and_hidden_by_moderator(client: AsyncClient) -> None:
    owner_csrf, _ = await register(client, "reportmessageowner")
    moderator = AsyncClient(transport=client._transport, base_url="http://testserver")
    try:
        moderator_csrf, moderator_id = await register(moderator, "reportmessagemoderator")
        conversation = await client.post(f"/api/v1/conversations/direct/{moderator_id}", headers={"X-CSRF-Token": owner_csrf})
        message = await client.post(f"/api/v1/conversations/{conversation.json()['id']}/messages", json=await encrypted_payload(client, "Report me"), headers={"X-CSRF-Token": owner_csrf})
        report = await moderator.post("/api/v1/reports", json={"message_id": message.json()["id"], "reason": "harassment", "details": "abuse"}, headers={"X-CSRF-Token": moderator_csrf})
        assert report.status_code == 201
        assert report.json()["target"]["kind"] == "message"

        async with client._transport.app.state.session_factory() as session:
            user = await session.scalar(select(User).where(User.username_normalized == "reportmessagemoderator"))
            user.role = "moderator"
            await session.commit()

        resolved = await moderator.patch(f"/api/v1/admin/reports/{report.json()['id']}", json={"status": "resolved", "resolution": "Removed", "hide_target": True}, headers={"X-CSRF-Token": moderator_csrf})
        assert resolved.status_code == 200
        assert resolved.json()["target"]["is_deleted"] is True
    finally:
        await moderator.aclose()
