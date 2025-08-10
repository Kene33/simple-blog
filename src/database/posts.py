import sqlite3
from typing import Optional
import aiosqlite
import json

DATABASE = "src/database/posts.db"


async def create_database() -> None:
    async with aiosqlite.connect(DATABASE) as db:
        create_table_query = f'''
        CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT NOT NULL,
        tags TEXT,
        createdAt TEXT NOT NULL,
        image_url TEXT,
        FOREIGN KEY (username) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE (username, title)  -- Запрещает одинаковые названия у одного пользователя
        )
        '''

        await db.execute(create_table_query)
        await db.commit()


async def check_user_exists(user_id: int) -> bool:
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute("SELECT * FROM posts WHERE user_id = ?", (user_id,)) as cursor:
            result = await cursor.fetchone()
            if result:
                return True

            return False

async def get_posts(user_id: Optional[int] = None, post_id: Optional[int] = None, tag: Optional[str] = None):
    base_query = "SELECT * FROM posts"
    params = []
    
    # Фильтруем по user_id, если он передан
    if user_id is not None:
        base_query += " WHERE user_id = ?"
        params.append(user_id)
    
    # Добавляем фильтрацию по post_id, если он передан
    if post_id is not None:
        # Если уже был WHERE, то используем AND для добавления условия
        if params:
            base_query += " AND id = ?"
        else:
            base_query += " WHERE id = ?"
        params.append(post_id)
    
    # Добавляем фильтрацию по tag, если он передан
    if tag is not None:
        # Если уже был WHERE, то используем AND для добавления условия
        if params:
            base_query += " AND tags LIKE ?"
        else:
            base_query += " WHERE tags LIKE ?"
        params.append(f"%{tag}%")
    
    # Сортируем по дате
    base_query += " ORDER BY createdAt DESC"
    
    # Выполнение запроса
    async with aiosqlite.connect(DATABASE) as db:
        async with db.execute(base_query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return rows

async def add_posts(username: str, title: str, content: str, category: str, tags: list, createdAt: int, image_url: str | None) -> bool:
    try:
        async with aiosqlite.connect(DATABASE) as db:
            tags_json = json.dumps(tags)

            await db.execute('''
            INSERT INTO posts (username, title, content, category, tags, createdAt, image_url) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (username, title, content, category, tags_json, createdAt, image_url))

            await db.commit()

            return {"ok": True}
    except sqlite3.IntegrityError:
        return {"ok": False, "message": "Ошибка нарушения уникального ограничения"}
    except Exception as e:
        return {"ok": False, "message": e}

async def delete_posts(user_id: int, post_id: int) -> bool:
    try:
        async with aiosqlite.connect(DATABASE) as db:
            await db.execute(f"DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, user_id))
            await db.commit()

            return True
    except:
        return False

async def find_posts_by_tag(tag: str, user_id: int = None) -> dict:
    async with aiosqlite.connect(DATABASE) as db:
        if user_id:
            query = "SELECT * FROM posts WHERE tags LIKE ? AND user_id = ?"
        else:
            query = "SELECT * FROM posts WHERE tags LIKE ?"
        param = f"%{tag}%"
        async with db.execute(query, (param,)) as cursor:
            rows = await cursor.fetchall()
            return rows

    


