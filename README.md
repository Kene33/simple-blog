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
