from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.modules.auth.schemas import UserSummary


class PostCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10_000)
    category: str = Field(min_length=1, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=10)
    media_ids: list[UUID] = Field(default_factory=list, max_length=4)

    @field_validator("title", "content", "category")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().casefold() for value in values]
        if any(not value or len(value) > 30 for value in normalized) or len(set(normalized)) != len(normalized):
            raise ValueError("Tags must be unique non-empty strings up to 30 characters")
        return normalized


class PostUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=10_000)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    tags: list[str] | None = Field(default=None, max_length=10)
    media_ids: list[UUID] | None = Field(default=None, max_length=4)

    @field_validator("title", "content", "category")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator("tags")
    @classmethod
    def normalize_optional_tags(cls, values: list[str] | None) -> list[str] | None:
        return PostCreateRequest.normalize_tags(values) if values is not None else None

    def has_changes(self) -> bool:
        return any(getattr(self, field) is not None for field in self.model_fields_set)


class PostRead(BaseModel):
    id: UUID
    author: UserSummary
    title: str
    content: str
    category: str
    tags: list[str]
    media: list[object] = Field(default_factory=list)
    like_count: int
    comment_count: int
    share_count: int
    liked_by_me: bool = False
    created_at: datetime
    updated_at: datetime


class PostPage(BaseModel):
    items: list[PostRead]
    next_cursor: str | None = None
