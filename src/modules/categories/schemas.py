from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.modules.posts.schemas import CategoryRequestRead


class CategoryRequestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Category name must not be blank")
        return value


class CategoryRequestUpdate(BaseModel):
    status: Literal["approved", "rejected"]
    resolution: str | None = Field(default=None, max_length=2_000)

    @field_validator("resolution")
    @classmethod
    def strip_resolution(cls, value: str | None) -> str | None:
        return value.strip() or None if value else None


class CategoryRequestPage(BaseModel):
    items: list[CategoryRequestRead]
    next_cursor: str | None = None


class CategoryRequestAdminRead(CategoryRequestRead):
    requester_id: UUID
    created_at: datetime
    resolved_at: datetime | None
