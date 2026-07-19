import asyncio
from datetime import datetime, timedelta, timezone

from src.db.session import engine, session_factory
from src.modules.media.service import cleanup_orphan_media
from src.modules.media.storage import S3Storage
from src.core.config import get_settings


async def main() -> None:
    async with session_factory() as session:
        count = await cleanup_orphan_media(session, S3Storage(get_settings()), datetime.now(timezone.utc) - timedelta(hours=24))
        await session.commit()
    await engine.dispose()
    print(f"Deleted {count} orphan media object(s)")


if __name__ == "__main__":
    asyncio.run(main())
