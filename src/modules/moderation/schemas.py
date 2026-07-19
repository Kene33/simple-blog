from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ReportCreateRequest(BaseModel):
    post_id: UUID | None = None
    comment_id: UUID | None = None
    reason: Literal["spam", "harassment", "illegal", "other"]
    details: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_target(self) -> "ReportCreateRequest":
        if (self.post_id is None) == (self.comment_id is None):
            raise ValueError("Exactly one target is required")
        if self.details is not None:
            self.details = self.details.strip() or None
        return self
