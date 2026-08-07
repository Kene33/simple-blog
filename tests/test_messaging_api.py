import pytest
from httpx import AsyncClient


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
