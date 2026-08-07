# Messaging E2EE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace plaintext direct and group message transport/storage with client-encrypted envelopes.

**Architecture:** Each browser device generates a P-256 ECDH key pair. The API stores only the public JWK and returns conversation members' public keys. The sender derives a shared key per recipient device, encrypts the message with AES-GCM, and sends one opaque envelope containing recipient ciphertexts. The server persists and relays the envelope without decrypting or searching it.

**Tech Stack:** FastAPI, PostgreSQL, SQLAlchemy async, Alembic, React, browser Web Crypto API, IndexedDB.

## Global Constraints

- Private keys never enter API requests, PostgreSQL, Redis, logs, or localStorage.
- Existing authenticated membership, CSRF, rate limits, and media ownership checks remain mandatory.
- Existing plaintext messages are legacy data and must not be returned as plaintext after the migration.
- Server-side message search is removed; frontend searches locally decrypted messages.
- Each implementation step gets a focused test and a separate commit.

### Task 1: Device key registry

**Files:** `src/db/models.py`, `src/db/models_registry.py`, `src/modules/messaging/schemas.py`, `src/modules/messaging/service.py`, `src/api/messaging.py`, new Alembic migration, `tests/test_messaging_api.py`.

- Add `messaging_devices` with owner, public JWK, label, revocation timestamp, and timestamps.
- Add authenticated create/list/revoke endpoints for the current user's devices.
- Add a member-only endpoint returning active public devices for a conversation.
- Reject malformed public JWK and revoked devices.

### Task 2: Encrypted message contract

**Files:** `src/db/models.py`, `src/modules/messaging/schemas.py`, `src/modules/messaging/service.py`, `src/api/messaging.py`, migration, `tests/test_messaging_api.py`.

- Replace message request `body` with bounded `envelope` JSON.
- Persist only serialized envelope data for new messages.
- Return envelopes unchanged to authorized members and tombstones for deleted messages.
- Remove server-side plaintext search and return a clear `409` contract error for the old endpoint.
- Preserve media, ownership, edit/delete, read markers, retention, and WebSocket events.

### Task 3: Browser key storage and encryption

**Files:** `src/frontend/src/lib/messageCrypto.js`, `src/frontend/src/lib/messagesSocket.js`, `src/frontend/src/pages/MessagesPage.jsx`, `src/frontend/src/lib/messages.check.mjs`.

- Generate/import/export public JWK with Web Crypto.
- Store private CryptoKey in IndexedDB only.
- Register the device public key once and fetch conversation devices before sending.
- Encrypt each message with AES-GCM and derive recipient keys with ECDH + HKDF.
- Decrypt incoming/history envelopes locally; show an explicit unavailable-message state if a private key is missing.
- Keep typing and read events unencrypted because they contain no message content.

### Task 4: Recovery and product contract

**Files:** `src/frontend/src/lib/messageCrypto.js`, `src/frontend/src/pages/MessagesPage.jsx`, `docs/messaging-e2ee-decision.md`, `docs/api-v1.md`, `docs/api-schemas.md`, roadmap file.

- Add a local recovery phrase flow that encrypts the device private-key backup before it can leave the browser.
- Never send or persist the recovery phrase itself.
- Document device loss, revocation, legacy messages, local-only search, and current MVP limitation: this is authenticated E2EE at rest/in transit, not a full Signal ratchet.

### Task 5: Verification and release

**Files:** backend/frontend tests and docs only as needed.

- Run backend tests, Ruff, frontend checks/build, browser smoke, and migration validation.
- Verify two production accounts can exchange encrypted messages over WSS.
- Update graphify and mark only evidenced roadmap items complete.
- Commit each task and push `main`.
