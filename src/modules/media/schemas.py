from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel


MediaPurpose = Literal["avatar", "post"]


class MediaRead(BaseModel):
    id: UUID
    kind: str
    mime_type: str
    size_bytes: int
    url: str
    status: str
    created_at: datetime
