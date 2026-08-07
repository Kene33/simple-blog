import asyncio
import os
from urllib.parse import urlparse

import httpx
import websockets


async def main() -> None:
    base_url = os.environ.get("MESSAGING_BASE_URL", "https://simple-blog-delta-roan.vercel.app")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("MESSAGING_BASE_URL must be an HTTPS URL")
    access_cookie = os.environ.get("MESSAGING_ACCESS_COOKIE")
    if not access_cookie:
        identifier = os.environ.get("MESSAGING_IDENTIFIER")
        password = os.environ.get("MESSAGING_PASSWORD")
        if not identifier or not password:
            raise SystemExit("Set MESSAGING_ACCESS_COOKIE or MESSAGING_IDENTIFIER and MESSAGING_PASSWORD")
        async with httpx.AsyncClient(base_url=base_url, follow_redirects=True) as client:
            response = await client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})
            if response.status_code != 200:
                raise SystemExit(f"Production login failed: HTTP {response.status_code}")
            access_cookie = client.cookies.get("access_token")
        if not access_cookie:
            raise SystemExit("Production login did not return access_token")
    ws_url = f"wss://{parsed.netloc}/api/v1/ws/messages"
    origin = os.environ.get("MESSAGING_ORIGIN", base_url.rstrip("/"))
    async with websockets.connect(ws_url, origin=origin, additional_headers={"Cookie": f"access_token={access_cookie}"}, open_timeout=15, close_timeout=5) as socket:
        await socket.send('{"type":"ping"}')
        response = await asyncio.wait_for(socket.recv(), timeout=10)
        if response != '{"type":"pong"}':
            raise SystemExit(f"Unexpected WebSocket response: {response}")
    print(f"Authenticated WSS passed: {ws_url}")


if __name__ == "__main__":
    asyncio.run(main())
