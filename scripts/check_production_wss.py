import asyncio
import os
from urllib.parse import urlparse

import websockets


async def main() -> None:
    base_url = os.environ.get("MESSAGING_BASE_URL", "https://simple-blog-delta-roan.vercel.app")
    access_cookie = os.environ.get("MESSAGING_ACCESS_COOKIE")
    if not access_cookie:
        raise SystemExit("MESSAGING_ACCESS_COOKIE is required")
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit("MESSAGING_BASE_URL must be an HTTPS URL")
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
