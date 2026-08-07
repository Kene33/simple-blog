from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

MediaPurpose = Literal["avatar", "post", "cover", "message"]


class MediaRead(BaseModel):
    id: UUID
    kind: str
    purpose: MediaPurpose
    mime_type: str
    size_bytes: int
    url: str
    status: str
    created_at: datetime
