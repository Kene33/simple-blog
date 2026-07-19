from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class LikeRead(BaseModel):
    post_id: UUID
    like_count: int
    liked_by_me: bool


class ShareCreateRequest(BaseModel):
    channel: Literal["copy", "native"]


class ShareRead(BaseModel):
    post_id: UUID
    canonical_url: str
    share_count: int
