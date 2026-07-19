# Simple Blog

Социальный блог с модульным FastAPI backend и frontend на HTML, CSS и vanilla JavaScript.

## Backend

- FastAPI, SQLAlchemy 2 async, PostgreSQL и Alembic
- JWT access/refresh cookies, CSRF и роли `user`/`admin`
- REST API `/api/v1`: пользователи, посты, теги, поиск, медиа, комментарии, лайки, sharing и moderation
- S3-compatible media storage: MinIO в development
- Cursor pagination, soft-delete, structured errors и request IDs

Контракты: [API v1](docs/api-v1.md), [схемы](docs/api-schemas.md), [архитектура](docs/architecture.md).

## Запуск

Нужны Docker и Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

API будет доступен на `http://localhost:8000`, OpenAPI — на `http://localhost:8000/docs`.

Для запуска без Docker нужны PostgreSQL и MinIO, настроенные через `.env`:

```bash
alembic upgrade head
uvicorn src.main:app --reload --port 4000
```

## Проверки backend

```bash
ruff check src tests
pytest -q tests
alembic upgrade head --sql
```

GitHub Actions поднимает чистый PostgreSQL, применяет миграции и запускает весь
набор тестов, включая проверку конкурентных likes.

## Backend roadmap

- [x] Архитектура, FastAPI-каркас, PostgreSQL и миграции
- [x] Аутентификация, профили и роли
- [x] Посты, теги, cursor pagination и full-text search
- [x] Media upload через S3/MinIO
- [x] Древовидные комментарии и tombstones
- [x] Idempotent likes и share events
- [x] Жалобы и admin moderation
- [x] Финальный PostgreSQL прогон в CI

Локальный рабочий roadmap: `ROADMAP.md` (намеренно не отслеживается Git).

## Prompt для проектирования frontend

```text
Спроектируй интерфейс веб-соцсети Simple Blog. Не задавай визуальный стиль,
цветовую палитру, шрифты или декоративные приёмы. Опиши только состав экранов,
компоненты, данные и пользовательские сценарии. Интерфейс работает с REST API
`/api/v1`, использует HTML, CSS и vanilla JavaScript.

Нужны следующие экраны и состояния:

1. Общая навигация
   - Ссылки на ленту, вход, регистрацию, собственный профиль и выход.
   - Состояния для гостя, авторизованного пользователя и администратора.
   - Место для уведомлений об успешных действиях и ошибках API.

2. Лента постов и поиск
   - Список постов из `GET /posts`.
   - Поиск по `query` с выбором `search_in=all|title|content`.
   - Фильтры `tag`, `category`, `author`, сортировка `newest|oldest`.
   - Синхронизация фильтров с URL.
   - Cursor pagination с кнопкой «Показать ещё» и состояниями загрузки,
     пустого результата и ошибки.
   - Карточка поста: автор и avatar, заголовок, текст, категория, теги,
     вложения, дата создания/изменения, количество лайков, комментариев и
     share, признак `liked_by_me`, переход к полному посту.

3. Страница поста
   - Полные данные `GET /posts/{post_id}`.
   - Для автора: редактирование и удаление поста.
   - Создание и редактирование поста: title, content, category, до 10 тегов,
     до 4 заранее загруженных вложений, из которых видео может быть только одно.
   - Для изображений и видео: выбор файла, preview, прогресс, удаление из
     списка перед публикацией и обработка частичной ошибки upload.
   - Лайк через `PUT`/`DELETE /posts/{post_id}/like` с optimistic update и
     откатом при ошибке.
   - Sharing через Web Share API или копирование ссылки; после действия
     отправлять `POST /posts/{post_id}/shares` с `channel=copy|native`.
   - Кнопка жалобы на пост.

4. Комментарии на странице поста
   - Корневые комментарии из `GET /posts/{post_id}/comments`.
   - Отдельная загрузка ответов по `parent_id`, без загрузки всего дерева сразу.
   - Создание корневого комментария или ответа, редактирование и удаление
     собственного комментария.
   - Для удалённого комментария показывать tombstone, но сохранять видимыми
     его ответы.
   - Cursor pagination для корневых комментариев и ответов.
   - Кнопка жалобы на комментарий.

5. Регистрация и сессия
   - Регистрация: username, email, password; вход: identifier и password.
   - Поля ошибок валидации, состояния отправки и ошибки авторизации.
   - Сессия использует HttpOnly cookies: не хранить JWT в localStorage.
   - Для изменяющих запросов передавать CSRF header; при истечении access
     cookie выполнять refresh и повторять безопасный запрос.
   - Logout очищает интерфейс авторизованного пользователя.

6. Профили
   - Собственный профиль из `GET /users/me`: username, email, avatar,
     количество постов, даты; редактирование username, email и avatar.
   - Public profile из `GET /users/{username}` без email и роли.
   - Avatar загружается отдельно через `POST /media` с `purpose=avatar`, затем
     его ID передаётся в `PATCH /users/me`.

7. Жалобы и moderation
   - Модальное окно жалобы: причина `spam|harassment|illegal|other` и
     необязательные details; отправка в `POST /reports` только для одного
     объекта: поста или комментария.
   - Обработать повторную открытую жалобу как понятное состояние интерфейса.
   - Только для admin: страница очереди `GET /admin/reports` с фильтром статуса,
     pagination, данными о репортёре и объекте жалобы.
   - Admin может изменить открытую жалобу на `resolved` или `rejected` через
     `PATCH /admin/reports/{report_id}` и оставить resolution.

8. Общие требования к поведению
   - Поддержать loading, empty, error, forbidden и not-found состояния.
   - Не использовать небезопасный `innerHTML` для пользовательских данных.
   - Учитывать 401, 403, 404, 409, 413, 415 и 422 ответы API.
   - Не добавлять отсутствующие в API функции: подписки, внутренние репосты,
     личные сообщения, уведомления, восстановление пароля, рекомендации и
     видеотранскодирование.
```

## Структура

```text
src/
  api/       HTTP routers
  core/      configuration, security, logging, errors
  db/        async sessions and SQLAlchemy models
  modules/   domain services
  frontend/  HTML, CSS and JavaScript
docs/        architecture and API contracts
alembic/     PostgreSQL migrations
tests/       API and PostgreSQL integration tests
```

## License

MIT
