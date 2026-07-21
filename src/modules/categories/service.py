import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.errors import AppError
from src.db.models import Category, CategoryRequest, Post, User
from src.modules.categories.schemas import CategoryRequestAdminRead, CategoryRequestCreate, CategoryRequestPage, CategoryRequestUpdate
from src.modules.posts.schemas import CategoryRead, CategoryRequestRead


def normalize_category(value: str) -> str:
    return value.strip().casefold()


def as_category(category: Category | None) -> CategoryRead | None:
    return CategoryRead(id=category.id, name=category.name, status=category.status) if category else None


def as_request(request: CategoryRequest | None, category: Category | None) -> CategoryRequestRead | None:
    return CategoryRequestRead(id=request.id, name=category.name if category else "", status=request.status, resolution=request.resolution) if request else None


async def list_categories(session: AsyncSession) -> list[CategoryRead]:
    categories = (await session.scalars(select(Category).where(Category.status == "approved").order_by(Category.name_normalized))).all()
    return [as_category(category) for category in categories if category]


async def create_category_request(session: AsyncSession, user: User, payload: CategoryRequestCreate) -> CategoryRequest:
    normalized = normalize_category(payload.name)
    category = await session.scalar(select(Category).where(Category.name_normalized == normalized))
    if category is not None and category.status != "rejected":
        raise AppError("RESOURCE_CONFLICT", "Category already exists or is pending", 409)
    if category is None:
        category = Category(name=payload.name, name_normalized=normalized, status="pending")
        session.add(category)
        await session.flush()
    else:
        category.name = payload.name
        category.status = "pending"
    request = CategoryRequest(requester_id=user.id, category_id=category.id, status="pending")
    session.add(request)
    await session.flush()
    return request


async def resolve_category_selection(session: AsyncSession, *, category_id: UUID | None, category_request_id: UUID | None, category_name: str | None = None) -> tuple[Category, CategoryRequest | None]:
    if category_id is not None:
        category = await session.scalar(select(Category).where(Category.id == category_id, Category.status == "approved"))
        if category is None:
            raise AppError("VALIDATION_ERROR", "Category must be approved", 422)
        return category, None
    if category_name is not None:
        category = await session.scalar(select(Category).where(Category.name_normalized == normalize_category(category_name), Category.status == "approved"))
        if category is None:
            raise AppError("VALIDATION_ERROR", "Category must be approved", 422)
        return category, None
    request = await session.scalar(select(CategoryRequest).where(CategoryRequest.id == category_request_id))
    if request is None or request.status != "pending":
        raise AppError("RESOURCE_CONFLICT", "Category request is no longer pending", 409)
    category = await session.get(Category, request.category_id)
    if category is None or category.status != "pending":
        raise AppError("RESOURCE_CONFLICT", "Category request is no longer pending", 409)
    return category, request


async def category_request_for(session: AsyncSession, request_id: UUID | None) -> tuple[CategoryRequest | None, Category | None]:
    if request_id is None:
        return None, None
    request = await session.get(CategoryRequest, request_id)
    return request, await session.get(Category, request.category_id) if request else None


async def list_own_requests(session: AsyncSession, user_id: UUID) -> list[CategoryRequestRead]:
    rows = (await session.execute(select(CategoryRequest, Category).join(Category, Category.id == CategoryRequest.category_id).where(CategoryRequest.requester_id == user_id).order_by(CategoryRequest.created_at.desc()))).all()
    return [as_request(request, category) for request, category in rows if as_request(request, category)]


def _scope(status: str) -> str:
    return hashlib.sha256(status.encode()).hexdigest()


def _encode_cursor(request: CategoryRequest, scope: str, settings: Settings) -> str:
    payload = {"v": 1, "resource": "category_requests", "created_at": request.created_at.isoformat(), "id": str(request.id), "scope": scope}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_cursor(value: str, scope: str, settings: Settings) -> tuple[datetime, UUID]:
    try:
        encoded, signature = value.split(".", 1)
        expected = hmac.new(settings.jwt_secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if payload["v"] != 1 or payload["resource"] != "category_requests" or payload["scope"] != scope:
            raise ValueError
        return datetime.fromisoformat(payload["created_at"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None


async def list_admin_requests(session: AsyncSession, *, settings: Settings, status: str, cursor: str | None, limit: int) -> CategoryRequestPage:
    if status not in {"pending", "approved", "rejected"}:
        raise AppError("VALIDATION_ERROR", "Unsupported category request status", 422)
    scope = _scope(status)
    query = select(CategoryRequest, Category).join(Category, Category.id == CategoryRequest.category_id).where(CategoryRequest.status == status)
    sqlite_cursor_id: UUID | None = None
    if cursor:
        created_at, request_id = _decode_cursor(cursor, scope, settings)
        if session.bind and session.bind.dialect.name == "postgresql":
            query = query.where((CategoryRequest.created_at < created_at) | ((CategoryRequest.created_at == created_at) & (CategoryRequest.id < request_id)))
        else:
            sqlite_cursor_id = request_id
    rows = (await session.execute(query.order_by(CategoryRequest.created_at.desc(), CategoryRequest.id.desc()))).all() if sqlite_cursor_id else (await session.execute(query.order_by(CategoryRequest.created_at.desc(), CategoryRequest.id.desc()).limit(limit + 1))).all()
    if sqlite_cursor_id:
        try:
            rows = rows[[request.id for request, _ in rows].index(sqlite_cursor_id) + 1 : limit + 2]
        except ValueError:
            raise AppError("INVALID_CURSOR", "Cursor is invalid", 400) from None
    items = [CategoryRequestAdminRead(id=request.id, name=category.name, status=request.status, resolution=request.resolution, requester_id=request.requester_id, created_at=request.created_at, resolved_at=request.resolved_at) for request, category in rows[:limit]]
    next_cursor = _encode_cursor(rows[limit - 1][0], scope, settings) if len(rows) > limit else None
    return CategoryRequestPage(items=items, next_cursor=next_cursor)


async def resolve_category_request(session: AsyncSession, request_id: UUID, payload: CategoryRequestUpdate) -> CategoryRequest:
    request = await session.scalar(select(CategoryRequest).where(CategoryRequest.id == request_id).with_for_update())
    if request is None:
        raise AppError("RESOURCE_NOT_FOUND", "Category request not found", 404)
    if request.status != "pending":
        raise AppError("RESOURCE_CONFLICT", "Category request is already processed", 409)
    category = await session.get(Category, request.category_id)
    if category is None:
        raise AppError("RESOURCE_NOT_FOUND", "Category not found", 404)
    request.status = payload.status
    request.resolution = payload.resolution
    request.resolved_at = datetime.now(timezone.utc)
    category.status = payload.status
    if payload.status == "approved":
        await session.execute(update(Post).where(Post.category_request_id == request.id, Post.status == "pending_category").values(status="published", category_id=category.id, category=category.name, updated_at=datetime.now(timezone.utc)))
    else:
        await session.execute(update(Post).where(Post.category_request_id == request.id, Post.status == "pending_category").values(status="needs_category_change", category_id=None, updated_at=datetime.now(timezone.utc)))
    await session.flush()
    return request
