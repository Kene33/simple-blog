from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.modules.auth.schemas import UserSummary


class CommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2_000)
    parent_id: UUID | None = None

    @field_validator("body")
    @classmethod
    def strip_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Body must not be blank")
        return value


class CommentRead(BaseModel):
    id: UUID
    post_id: UUID
    author: UserSummary
    parent_id: UUID | None
    reply_count: int = 0
    body: str
    is_deleted: bool
    created_at: datetime
    updated_at: datetime


class CommentUpdateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=2_000)

    @field_validator("body")
    @classmethod
    def strip_body(cls, value: str) -> str:
        return CommentCreateRequest.strip_body(value)


class CommentPage(BaseModel):
    items: list[CommentRead]
    next_cursor: str | None = None
