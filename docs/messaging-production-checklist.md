# Messaging production checklist

## Verified locally

- PostgreSQL migrations reach `0022_messaging_devices (head)`.
- Two independent Uvicorn processes on ports `8101` and `8102` share one
  Redis instance.
- A WebSocket connected to instance B receives a message sent through REST on
  instance A: `TWO_INSTANCE_REDIS_WSS=PASS`.
- Redis bridge integration test passes with a real Redis service.
- `scripts/check_two_instance_realtime.py` verifies a message sent through
  instance A arrives on a WebSocket connected to instance B.
- Browser smoke passed locally for `/`, `/login`, `/messages`, and `/search`;
  no Vite error overlay or console errors were detected.
- Browser E2E covers offline state and WebSocket reconnect history resync; CI
  installs Chromium before running it.
- Retention service removes only soft-deleted messages older than the cutoff.

## Verified production

- Production database migration `0022_messaging_devices` is applied.
- Authenticated production WSS ping/pong passes.
- Two production accounts exchanged an opaque encrypted envelope through the
  production API and WebSocket path: `TWO_INSTANCE_REDIS_WSS=PASS`.

## Verify authenticated production WSS

Use a short-lived access-cookie value outside the repository:

```bash
MESSAGING_BASE_URL=https://your-production-domain \
MESSAGING_ACCESS_COOKIE='redacted-value' \
python scripts/check_production_wss.py
```

Alternatively, provide a dedicated test account without exposing its password
to the repository:

```bash
MESSAGING_BASE_URL=https://your-production-domain \
MESSAGING_IDENTIFIER=messaging-e2e-user \
MESSAGING_PASSWORD='redacted-value' \
python scripts/check_production_wss.py
```

The check validates HTTPS base URL, the production reverse proxy, the
authenticated WebSocket handshake, and the ping/pong protocol. The public
production domain responds to health checks and rejects unauthenticated
WebSocket handshakes with `403`.

## Required Vercel settings

- `REDIS_URL` pointing to a shared production Redis, not an instance-local
  Redis.
- `CRON_SECRET` for keepalive and message retention jobs.
- `MESSAGE_RETENTION_DAYS` according to the retention policy.
- `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, and `VAPID_SUBJECT` for push.
- Exact HTTPS `CORS_ORIGINS` and `PUBLIC_BASE_URL`.

For the two-instance check, use dedicated test accounts outside the
repository:

```bash
MESSAGING_INSTANCE_A=http://127.0.0.1:8101 \
MESSAGING_INSTANCE_B=http://127.0.0.1:8102 \
MESSAGING_IDENTIFIER_A=messaging-e2e-a \
MESSAGING_PASSWORD_A='redacted' \
MESSAGING_IDENTIFIER_B=messaging-e2e-b \
MESSAGING_PASSWORD_B='redacted' \
python scripts/check_two_instance_realtime.py
```
