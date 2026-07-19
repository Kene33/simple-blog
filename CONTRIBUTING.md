# Contributing

Спасибо за вклад в Simple Blog. Перед изменением выберите конкретную задачу,
проверьте её на чистой PostgreSQL и опишите результат в pull request.

## Локальный запуск

```bash
cp .env.example .env
docker compose up --build
```

Для backend-проверок:

```bash
ruff check src tests
pytest -q tests
alembic upgrade head --sql
```

## Правила изменений

- Добавляйте новые API-ресурсы под `/api/v1`.
- Обновляйте `docs/api-v1.md` и схемы вместе с изменением контракта.
- Проверяйте ownership, CSRF и роли на state-changing endpoints.
- Для миграций проверяйте чистый прогон `alembic upgrade head`.
- Не добавляйте секреты, `.env` и локальные базы в репозиторий.

## Pull request

Опишите в PR:

- что изменилось и зачем;
- какие тесты и миграции вы запустили;
- какие API-документы обновили;
- известные ограничения или следующие шаги.

Для ошибок и предложений используйте [GitHub Issues](https://github.com/Kene33/simple-blog/issues).
