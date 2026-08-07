import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.db.models import User


async def register(client: AsyncClient, username: str) -> tuple[str, str]:
    response = await client.post("/api/v1/auth/register", json={"username": username, "email": f"{username}@example.com", "password": "strong-password"})
    assert response.status_code == 201
    return client.cookies.get("csrf_token"), response.json()["user"]["id"]


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
        message = await client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"body": "Hello"}, headers={"X-CSRF-Token": owner_csrf})
        assert message.status_code == 201
        message_id = message.json()["id"]
        assert message.json()["sender"]["id"] == owner_id
        second_message = await client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"body": "Second"}, headers={"X-CSRF-Token": owner_csrf})
        assert second_message.status_code == 201

        assert (await other.get("/api/v1/conversations")).json()["items"][0]["id"] == conversation_id
        history = await other.get(f"/api/v1/conversations/{conversation_id}/messages", params={"limit": 1})
        assert history.status_code == 200
        assert history.json()["items"][0]["body"] == "Hello"
        next_history = await other.get(f"/api/v1/conversations/{conversation_id}/messages", params={"limit": 1, "cursor": history.json()["next_cursor"]})
        assert next_history.json()["items"][0]["body"] == "Second"
        assert (await client.post(f"/api/v1/users/{other_id}/block", headers={"X-CSRF-Token": owner_csrf})).status_code == 204
        blocked_send = await client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"body": "blocked"}, headers={"X-CSRF-Token": owner_csrf})
        assert blocked_send.status_code == 404
        assert (await client.delete(f"/api/v1/users/{other_id}/block", headers={"X-CSRF-Token": owner_csrf})).status_code == 204
        assert (await other.patch(f"/api/v1/messages/{message_id}", json={"body": "stolen"}, headers={"X-CSRF-Token": other_csrf})).status_code == 404
        assert (await other.patch(f"/api/v1/conversations/{conversation_id}/read", json={"message_id": message_id}, headers={"X-CSRF-Token": other_csrf})).status_code == 204

        outsider_csrf, _ = await register(outsider, "messageoutsider")
        assert (await outsider.get(f"/api/v1/conversations/{conversation_id}/messages")).status_code == 404
        assert (await outsider.post(f"/api/v1/conversations/{conversation_id}/messages", json={"body": "intrusion"}, headers={"X-CSRF-Token": outsider_csrf})).status_code == 404
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
        message = await client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"body": "Hello"}, headers={"X-CSRF-Token": owner_csrf})
        message_id = message.json()["id"]
        await client.patch(f"/api/v1/messages/{message_id}", json={"body": "Edited"}, headers={"X-CSRF-Token": owner_csrf})
        await client.delete(f"/api/v1/messages/{message_id}", headers={"X-CSRF-Token": owner_csrf})
        await other.patch(f"/api/v1/conversations/{conversation_id}/read", json={"message_id": message_id}, headers={"X-CSRF-Token": other.cookies.get("csrf_token")})
        assert [event[1] for event in events] == ["message.created", "message.updated", "message.deleted", "message.read"]
        assert events[0][2]["message"]["id"] == message_id
        assert events[1][2]["message"]["body"] == "Edited"
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
        message = await client.post(f"/api/v1/conversations/{conversation.json()['id']}/messages", json={"body": "Report me"}, headers={"X-CSRF-Token": owner_csrf})
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
