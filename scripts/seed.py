import asyncio
import os

from pwdlib import PasswordHash
from sqlalchemy import select

from src.db.models import User
from src.db.session import session_factory


async def seed_admin() -> None:
    username = os.environ.get("SEED_ADMIN_USERNAME", "admin")
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    if not password:
        raise SystemExit("SEED_ADMIN_PASSWORD is required")

    password_hash = PasswordHash.recommended()
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.email_normalized == email.lower()))
        user = result.scalar_one_or_none()
        if user is None:
            session.add(User(username=username, username_normalized=username.lower(), email=email, email_normalized=email.lower(), password_hash=password_hash.hash(password), role="admin"))
        else:
            user.role = "admin"
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed_admin())
