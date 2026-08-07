# Direct Messages: implementation status

Статус: базовая версия личных сообщений завершена и синхронизирована с
backend-контрактом.

## Реализовано

- [x] Direct и group conversations с cursor pagination.
- [x] История и поиск сообщений только для участников.
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

- Backend: `76 passed, 3 skipped`.
- Frontend message checks, build и production dependency audit проходят.
- Локальная проверка двух процессов: `TWO_INSTANCE_REDIS_WSS=PASS`.
- Browser smoke: без error overlay и console errors.
- Authenticated production WSS требует отдельного production cookie/account.

## Отдельно для E2EE

E2EE не включается автоматически: он меняет схему сообщения, поиск и
восстановление доступа. Требуется выбрать модель ключей. Рекомендуемый
вариант: per-device keys, recovery phrase для локально зашифрованного backup,
только encrypted envelopes на сервере и client-side search.
