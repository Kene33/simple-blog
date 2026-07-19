import asyncio
from uuid import UUID, uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from src.core.config import Settings


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.s3_bucket
        self.client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url, aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key, region_name=settings.s3_region, config=Config(signature_version="s3v4"))

    @staticmethod
    def key_for(owner_id: UUID, mime_type: str) -> str:
        extension = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp", "video/mp4": "mp4", "video/webm": "webm"}[mime_type]
        return f"uploads/{owner_id}/{uuid4()}.{extension}"

    async def put(self, key: str, content: bytes, mime_type: str) -> None:
        await self.ensure_bucket()
        await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=key, Body=content, ContentType=mime_type)

    async def ensure_bucket(self) -> None:
        try:
            await asyncio.to_thread(self.client.head_bucket, Bucket=self.bucket)
        except ClientError as error:
            if error.response["Error"].get("Code") not in {"404", "NoSuchBucket"}:
                raise
            await asyncio.to_thread(self.client.create_bucket, Bucket=self.bucket)

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)

    async def get(self, key: str) -> dict:
        return await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
