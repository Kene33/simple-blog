from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.errors import AppError
from src.db.models import Category
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, get_current_auth, require_admin, require_csrf
from src.modules.categories.schemas import CategoryRequestCreate, CategoryRequestPage, CategoryRequestUpdate
from src.modules.categories.service import as_request, create_category_request, list_admin_requests, list_categories, list_own_requests, resolve_category_request
from src.modules.posts.schemas import CategoryRead, CategoryRequestRead

router = APIRouter(prefix="/api/v1", tags=["categories"])


@router.get("/categories", response_model=list[CategoryRead])
async def list_all(session: AsyncSession = Depends(get_session)) -> list[CategoryRead]:
    return await list_categories(session)


@router.post("/category-requests", response_model=CategoryRequestRead, status_code=status.HTTP_201_CREATED)
async def create(payload: CategoryRequestCreate, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> CategoryRequestRead:
    request = await create_category_request(session, auth.user, payload)
    await session.commit()
    return as_request(request, await session.get(Category, request.category_id))


@router.get("/me/category-requests", response_model=list[CategoryRequestRead])
async def list_mine(auth: CurrentAuth = Depends(get_current_auth), session: AsyncSession = Depends(get_session)) -> list[CategoryRequestRead]:
    return await list_own_requests(session, auth.user.id)


@router.get("/admin/category-requests", response_model=CategoryRequestPage)
async def list_admin(status: str = "pending", cursor: str | None = None, limit: int = 20, _: CurrentAuth = Depends(require_admin), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> CategoryRequestPage:
    return await list_admin_requests(session, settings=settings, status=status, cursor=cursor, limit=min(max(limit, 1), 100))


@router.patch("/admin/category-requests/{request_id}", response_model=CategoryRequestRead)
async def resolve(request_id: UUID, payload: CategoryRequestUpdate, auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session)) -> CategoryRequestRead:
    if auth.user.role != "admin":
        raise AppError("FORBIDDEN", "Administrator role is required", 403)
    request = await resolve_category_request(session, request_id, payload)
    await session.commit()
    return as_request(request, await session.get(Category, request.category_id))
