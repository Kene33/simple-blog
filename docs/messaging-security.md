# Messaging security contract

## Scope

The first messaging release supports one-to-one text conversations. Messages
are stored in PostgreSQL and delivered over authenticated HTTPS/WebSocket
connections. End-to-end encryption is not part of this release; it requires a
separate audited key-management design.

## Security requirements

- PostgreSQL connections use SSL in production.
- Browser traffic uses HTTPS and `wss://` only.
- Access cookies authenticate WebSocket handshakes.
- The handshake validates the configured `Origin` allowlist.
- Every conversation read and message write verifies membership server-side.
- Banned, muted, or blocked users cannot send messages.
- Message bodies are plain text, trimmed, bounded, and never rendered as HTML.
- Message text is excluded from logs, metrics, traces, and error responses.
- REST and WebSocket message operations have independent rate limits.
- A message is committed to PostgreSQL before its realtime event is published.
- Redis Pub/Sub transports events only; it is not the source of message history.
- Reconnects resynchronize through the REST message cursor.

## Data retention

Messages use soft deletion for the first release so moderation and references
remain consistent. A later retention job may permanently delete old content
after the product policy and legal requirements are approved.

## Threats explicitly covered

- IDOR against conversations and messages.
- Forged author or recipient IDs.
- Cross-site WebSocket connections.
- Message spam and oversized payloads.
- Lost realtime events during reconnects.
- Cross-instance delivery failures on Vercel.

## Deferred

- End-to-end encryption.
- Group conversations.
- File attachments, reactions, typing indicators, and message search.
