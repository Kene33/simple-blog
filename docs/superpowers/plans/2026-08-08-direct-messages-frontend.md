# Direct Messages: implementation status

Статус: базовая версия личных сообщений завершена и синхронизирована с
backend-контрактом.

## Реализовано

- [x] Direct и group conversations с cursor pagination.
- [x] История для участников и client-side поиск по расшифрованной истории.
- [x] Отправка, редактирование, soft-delete и read markers.
- [x] HttpOnly-cookie auth, CSRF, membership/ban/mute/block проверки.
- [x] WebSocket `/api/v1/ws/messages` с Origin allowlist, heartbeat и typing.
- [x] Redis Pub/Sub для доставки между backend-инстансами.
- [x] REST resync истории после reconnect; дедупликация по `message.id`.
- [x] Вложения через private media с `purpose=message`.
- [x] Push subscription и service worker.
- [x] Жалобы на сообщения и retention для soft-deleted сообщений.
- [x] Browser smoke для `/`, `/login`, `/messages`, `/search`.
- [x] CI-проверки frontend и двух backend-инстансов с Redis.

## Проверки

- Backend: `78 passed, 3 skipped`.
- Frontend message checks, build и production dependency audit проходят.
- Локальная проверка двух процессов: `TWO_INSTANCE_REDIS_WSS=PASS`.
- Browser smoke: без error overlay и console errors.
- Authenticated production WSS требует отдельного production cookie/account.

## E2EE

- [x] Per-device P-256 keys with public-key registry.
- [x] AES-GCM encrypted envelopes for direct and group messages.
- [x] Private keys in IndexedDB and encrypted recovery backup helpers.
- [x] Client-side decryption; server-side plaintext search disabled.
- [ ] Signal-style ratchet and automatic key rotation require a separately
  audited protocol.
