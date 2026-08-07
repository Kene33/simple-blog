from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.modules.auth.schemas import UserSummary
from src.modules.media.schemas import MediaRead


class MessageCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4_000)
    media_ids: list[UUID] = Field(default_factory=list, max_length=4)

    @field_validator("body")
    @classmethod
    def strip_body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Body must not be blank")
        return value


class MessageUpdateRequest(MessageCreateRequest):
    pass


class MessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    sender: UserSummary
    body: str
    is_deleted: bool
    read_by_recipient: bool = False
    media: list[MediaRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MessagePage(BaseModel):
    items: list[MessageRead]
    next_cursor: str | None = None


class ConversationReadMarker(BaseModel):
    message_id: UUID


class ConversationMuteRequest(BaseModel):
    muted: bool


class ConversationRead(BaseModel):
    id: UUID
    kind: str = "direct"
    title: str | None = None
    participant: UserSummary
    participants: list[UserSummary] = Field(default_factory=list)
    last_message: MessageRead | None = None
    unread_count: int = 0
    muted: bool = False
    blocked: bool = False
    created_at: datetime
    updated_at: datetime


class ConversationPage(BaseModel):
    items: list[ConversationRead]
    next_cursor: str | None = None


class GroupCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    member_ids: list[UUID] = Field(default_factory=list, max_length=49)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title must not be blank")
        return value


class GroupMemberRequest(BaseModel):
    user_id: UUID
