# SIMPLY BLOG

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-0.68.0-009688?style=flat-square&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![SQLite](https://img.shields.io/badge/SQLite-3.0.0-003B57?style=flat-square&logo=sqlite)

</div>

## Описание

SIMPLE BLOG — это веб-приложение для управления публикациями блога. Проект построен на FastAPI и использует HTML/CSS/JavaScript для фронтенда. 

### Основные возможности

- JWT аутентификация
- Создание и управление постами
- Профили пользователей
- Категории и теги
- Темная тема
- Адаптивный дизайн

## Установка

### Необходимые зависимости

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic
- SQLite3

### Шаги по установке

1. **Клонируйте репозиторий:**
   ```bash
   git clone https://github.com/Kene33/simple-blog.git
   cd simple-blog
   ```

2. **Установите зависимости:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Запустите сервер:**
   ```bash
   python main.py
   ```

4. **Откройте frontend/index.html в браузере**

## API Endpoints

### Аутентификация

#### Регистрация
```http
POST /api/auth/register
Content-Type: application/json

{
    "username": "username",
    "password": "password"
}
```

#### Вход
```http
POST /api/auth/login
Content-Type: application/json

{
    "username": "username",
    "password": "password"
}
```

### Посты

#### Получение всех постов
```http
GET /api/posts
```

#### Создание поста
```http
POST /api/posts
Authorization: Bearer <token>
Content-Type: application/json

{
    "title": "Заголовок",
    "content": "Содержимое",
    "category": "Категория",
    "tags": ["tag1", "tag2"]
}
```

#### Удаление поста
```http
DELETE /api/posts/{post_id}
Authorization: Bearer <token>
```

### Пользователи

#### Информация о пользователе
```http
GET /api/user/{username}
```

## Фронтенд

Фронтенд часть приложения включает:

- Адаптивный дизайн
- Темная тема
- Модальные окна
- Система аутентификации
- Профиль пользователя
- Теги и категории

## TODO (только api)

- [ ] RESTful
- [x] JWT аутентификация
- [x] Базовый фронтенд
- [x] Создание постов
- [x] Удаление постов
- [x] Профиль пользователя
- [ ] Загрузка изображений
- [ ] Комментарии к постам
- [ ] Оценка постов
- [ ] Шаринг постов
- [ ] Поиск по тегам
- [ ] Поиск по названию
- [ ] Поиск по содержимому
- [ ] Сортировка по дате

## Структура проекта

```
blog-api/
├── src/
│   ├── api/           # FastAPI эндпоинты
│   │   ├── posts.py   # Эндпоинты для постов
│   │   ├── users.py   # Эндпоинты для пользователей
│   │   └── images.py  # Эндпоинты для изображений
│   ├── database/      # Работа с базой данных
│   │   ├── posts.py   # Модели и операции с постами
│   │   └── users.py   # Модели и операции с пользователями
│   ├── schemas/       # Pydantic модели
│   │   ├── posts.py   # Схемы для постов
│   │   └── users.py   # Схемы для пользователей
│   └── frontend/      # Фронтенд часть
│       ├── index.html    # Главная страница
│       ├── login.html    # Страница входа
│       ├── register.html # Страница регистрации
│       ├── profile.html  # Страница профиля
│       ├── main.js       # Основной JavaScript
│       └── style.css     # Стили
└── requirements.txt   # Зависимости Python
```

## Лицензия

MIT License
