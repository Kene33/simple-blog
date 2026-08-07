from pydantic import AnyHttpUrl, BaseModel, Field


class PushSubscriptionRequest(BaseModel):
    endpoint: AnyHttpUrl
    p256dh: str = Field(min_length=16, max_length=255)
    auth: str = Field(min_length=8, max_length=255)
