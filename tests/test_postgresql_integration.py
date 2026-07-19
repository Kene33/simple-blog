import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.errors import AppError
from src.db.models import Comment, Post, PostLike, User
from src.modules.comments.service import delete_comment, get_comment
from src.modules.interactions.service import like_post


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_postgresql_concurrent_likes_are_counted_once() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    async with session_factory() as session:
        user = User(username=f"like{suffix}", username_normalized=f"like{suffix}", email=f"like{suffix}@example.com", email_normalized=f"like{suffix}@example.com", password_hash="test")
        session.add(user)
        await session.flush()
        post = Post(author_id=user.id, title="Post", content="content", category="test")
        session.add(post)
        await session.commit()
        user_id, post_id = user.id, post.id

    async def like_once() -> None:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            await like_post(session, post_id, user)
            await session.commit()

    await asyncio.gather(*(like_once() for _ in range(8)))
    async with session_factory() as session:
        post = await session.get(Post, post_id)
        count = await session.scalar(select(func.count()).select_from(PostLike).where(PostLike.post_id == post_id))
        assert post.like_count == 1
        assert count == 1
        await session.delete(post)
        await session.delete(await session.get(User, user_id))
        await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.postgres
async def test_postgresql_concurrent_comment_deletes_decrement_once() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    engine = create_async_engine(url)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    suffix = uuid4().hex[:12]
    async with session_factory() as session:
        user = User(username=f"comment{suffix}", username_normalized=f"comment{suffix}", email=f"comment{suffix}@example.com", email_normalized=f"comment{suffix}@example.com", password_hash="test")
        session.add(user)
        await session.flush()
        post = Post(author_id=user.id, title="Post", content="content", category="test", comment_count=1)
        session.add(post)
        await session.flush()
        comment = Comment(post_id=post.id, author_id=user.id, body="comment")
        session.add(comment)
        await session.commit()
        user_id, post_id, comment_id = user.id, post.id, comment.id

    async def delete_once() -> bool:
        async with session_factory() as session:
            user = await session.get(User, user_id)
            try:
                await delete_comment(session, await get_comment(session, comment_id, user.id))
                await session.commit()
                return True
            except AppError:
                await session.rollback()
                return False

    results = await asyncio.gather(delete_once(), delete_once())
    assert results.count(True) == 1
    async with session_factory() as session:
        post = await session.get(Post, post_id)
        comment = await session.get(Comment, comment_id)
        assert post.comment_count == 0
        assert comment.deleted_at is not None
        await session.delete(post)
        await session.delete(await session.get(User, user_id))
        await session.commit()
    await engine.dispose()
