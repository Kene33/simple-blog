from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.modules.auth.schemas import UserSummary


class ReportCreateRequest(BaseModel):
    post_id: UUID | None = None
    comment_id: UUID | None = None
    message_id: UUID | None = None
    reason: Literal["spam", "harassment", "illegal", "other"]
    details: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_target(self) -> "ReportCreateRequest":
        if sum(value is not None for value in (self.post_id, self.comment_id, self.message_id)) != 1:
            raise ValueError("Exactly one target is required")
        if self.details is not None:
            self.details = self.details.strip() or None
        return self


class ReportUpdateRequest(BaseModel):
    status: Literal["resolved", "rejected"]
    resolution: str | None = Field(default=None, max_length=2_000)
    hide_target: bool = False
    ban_author: bool = False

    @model_validator(mode="after")
    def strip_resolution(self) -> "ReportUpdateRequest":
        if self.resolution is not None:
            self.resolution = self.resolution.strip() or None
        if self.status == "rejected" and (self.hide_target or self.ban_author):
            raise ValueError("Content or author actions require a resolved report")
        return self


class ReportTarget(BaseModel):
    kind: Literal["post", "comment", "message"]
    id: UUID
    title: str | None = None
    body: str | None = None
    is_deleted: bool = False


class ReportRead(BaseModel):
    id: UUID
    reporter: UserSummary
    post_id: UUID | None
    comment_id: UUID | None
    message_id: UUID | None
    reason: str
    details: str | None
    status: str
    resolution: str | None
    created_at: datetime
    resolved_at: datetime | None
    target: ReportTarget | None = None


class ReportCount(BaseModel):
    open_count: int


class UserModerationRequest(BaseModel):
    action: Literal["ban", "unban", "mute", "unmute"]
    muted_until: datetime | None = None
    reason: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_mute(self) -> "UserModerationRequest":
        if self.action == "mute" and self.muted_until is None:
            raise ValueError("muted_until is required when muting")
        return self


class AdminUserRead(UserSummary):
    email: str
    role: str
    disabled_at: datetime | None
    muted_until: datetime | None
    moderation_reason: str | None


class ReportPage(BaseModel):
    items: list[ReportRead]
    next_cursor: str | None = None


class UserRoleRequest(BaseModel):
    role: Literal["user", "moderator"]
    reason: str = Field(min_length=1, max_length=2_000)


class ModerationActionRead(BaseModel):
    id: UUID
    actor: UserSummary
    action: str
    target_type: str
    target_id: UUID
    reason: str | None
    created_at: datetime


class ModerationActionPage(BaseModel):
    items: list[ModerationActionRead]
    next_cursor: str | None = None


class ContentModerationRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2_000)
