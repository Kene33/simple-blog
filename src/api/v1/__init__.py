from fastapi import APIRouter

from src.api.auth import router as auth_router
from src.api.media import router as media_router
from src.api.posts import router as posts_router
from src.api.users import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(media_router)
router.include_router(posts_router)
router.include_router(users_router)
