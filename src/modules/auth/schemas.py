from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError("Username may contain only letters, numbers, and underscores")
        return value.strip()


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetRequestRead(BaseModel):
    message: str


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)
    password: str = Field(min_length=10, max_length=128)


class UserSummary(BaseModel):
    id: UUID
    username: str
    avatar_url: str | None = None
    status: Literal["active", "banned", "deleted"]
    is_banned: bool
    is_deleted: bool


class UserProfile(UserSummary):
    display_name: str | None = None
    bio: str | None = None
    cover_url: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    profile_visibility: Literal["public", "private"]
    posts_visibility: Literal["public", "private"]
    comments_visibility: Literal["public", "private"]
    posts_count: int
    created_at: datetime
    updated_at: datetime


class PublicUserProfile(UserSummary):
    display_name: str | None = None
    bio: str | None = None
    cover_url: str | None = None
    posts_count: int
    created_at: datetime
    updated_at: datetime


class ActiveAuthorRead(BaseModel):
    author: UserSummary
    posts_count: int
    likes_count: int


class UserUpdateRequest(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=30)
    email: EmailStr | None = None
    avatar_media_id: UUID | None = None
    cover_media_id: UUID | None = None
    display_name: str | None = Field(default=None, max_length=80)
    bio: str | None = Field(default=None, max_length=500)
    profile_visibility: Literal["public", "private"] | None = None
    posts_visibility: Literal["public", "private"] | None = None
    comments_visibility: Literal["public", "private"] | None = None
    current_password: str | None = Field(default=None, min_length=1, max_length=128)
    new_password: str | None = Field(default=None, min_length=10, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is not None and not value.replace("_", "").isalnum():
            raise ValueError("Username may contain only letters, numbers, and underscores")
        return value.strip() if value else value

    @field_validator("display_name", "bio")
    @classmethod
    def strip_profile_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    def has_changes(self) -> bool:
        return bool(self.model_fields_set)


class SessionRead(BaseModel):
    user: UserSummary
    access_expires_at: datetime
    refresh_expires_at: datetime
