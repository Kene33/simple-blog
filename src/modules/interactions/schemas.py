from uuid import UUID

from pydantic import BaseModel


class LikeRead(BaseModel):
    post_id: UUID
    like_count: int
    liked_by_me: bool
