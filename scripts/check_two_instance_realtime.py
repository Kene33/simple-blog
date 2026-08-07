import asyncio
import os
import uuid

import httpx
import websockets


async def login(client: httpx.AsyncClient, identifier: str, password: str) -> None:
    response = await client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
    if response.status_code != 200:
        raise SystemExit(f"Login failed for {identifier}: HTTP {response.status_code}")


async def register_device(client: httpx.AsyncClient, label: str) -> dict[str, object]:
    origin = str(client.base_url).rstrip("/")
    response = await client.post("/api/v1/messaging/devices", json={"public_key": {"kty": "EC", "crv": "P-256", "x": label, "y": "key"}, "label": label}, headers={"X-CSRF-Token": client.cookies.get("csrf_token"), "Origin": origin, "Referer": f"{origin}/"})
    if response.status_code != 201:
        raise SystemExit(f"Device registration failed: HTTP {response.status_code}")
    return response.json()


async def main() -> None:
    instance_a = os.environ.get("MESSAGING_INSTANCE_A", "http://127.0.0.1:8101")
    instance_b = os.environ.get("MESSAGING_INSTANCE_B", "http://127.0.0.1:8102")
    identifier_a = os.environ.get("MESSAGING_IDENTIFIER_A")
    password_a = os.environ.get("MESSAGING_PASSWORD_A")
    identifier_b = os.environ.get("MESSAGING_IDENTIFIER_B")
    password_b = os.environ.get("MESSAGING_PASSWORD_B")
    if not all((identifier_a, password_a, identifier_b, password_b)):
        raise SystemExit("Set MESSAGING_IDENTIFIER_A/PASSWORD_A and MESSAGING_IDENTIFIER_B/PASSWORD_B")

    async with httpx.AsyncClient(base_url=instance_a) as client_a, httpx.AsyncClient(base_url=instance_b) as client_b:
        await login(client_a, identifier_a, password_a)
        await login(client_b, identifier_b, password_b)
        device_a = await register_device(client_a, "ci-a")
        device_b = await register_device(client_b, "ci-b")
        user_b = (await client_b.get(f"/api/v1/users/{identifier_b}")).json()
        origin_a = str(client_a.base_url).rstrip("/")
        mutation_headers = {"X-CSRF-Token": client_a.cookies.get("csrf_token"), "Origin": origin_a, "Referer": f"{origin_a}/"}
        conversation = await client_a.post(f"/api/v1/conversations/direct/{user_b['id']}", headers=mutation_headers)
        if conversation.status_code not in {200, 201}:
            raise SystemExit(f"Conversation creation failed: HTTP {conversation.status_code}")
        conversation_id = conversation.json()["id"]
        access_cookie = client_b.cookies.get("access_token")
        ws_url = instance_b.replace("https://", "wss://").replace("http://", "ws://") + "/api/v1/ws/messages"
        async with websockets.connect(ws_url, origin=instance_b, additional_headers={"Cookie": f"access_token={access_cookie}"}) as socket:
            ciphertext = uuid.uuid4().hex
            envelope = {"version": 1, "sender_device_id": device_a["id"], "recipients": [{"device_id": device_a["id"], "iv": "a", "ciphertext": ciphertext}, {"device_id": device_b["id"], "iv": "b", "ciphertext": ciphertext}]}
            sent = await client_a.post(f"/api/v1/conversations/{conversation_id}/messages", json={"envelope": envelope}, headers=mutation_headers)
            if sent.status_code != 201:
                raise SystemExit(f"Message send failed: HTTP {sent.status_code}")
            event = await asyncio.wait_for(socket.recv(), timeout=10)
            if ciphertext not in event:
                raise SystemExit(f"Unexpected event: {event}")
    print("TWO_INSTANCE_REDIS_WSS=PASS")


if __name__ == "__main__":
    asyncio.run(main())
