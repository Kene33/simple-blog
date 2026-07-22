from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Simple Blog API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "production"
    host: str = "127.0.0.1"
    port: int = 4000
    reload: bool = True
    log_level: str = "INFO"
    cors_origins: str = "http://127.0.0.1:4000,http://127.0.0.1:5500"
    database_url: str = "postgresql+asyncpg://blog:blog@localhost:5432/blog"
    jwt_secret_key: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    password_reset_minutes: int = 30
    access_cookie_name: str = "access_token"
    refresh_cookie_name: str = "refresh_token"
    csrf_cookie_name: str = "csrf_token"
    csrf_header_name: str = "X-CSRF-Token"
    cookie_samesite: str = "lax"
    cookie_secure: bool = True
    cookie_domain: str | None = None
    public_base_url: str = "http://localhost:4000"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "simple-blog-media"
    s3_access_key: str = "minio"
    s3_secret_key: str = "minio-password"
    s3_region: str = "us-east-1"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    redis_url: str | None = None
    media_quota_bytes: int = 1_073_741_824
    media_quota_files: int = 100
    media_pending_limit: int = 10
    slow_request_ms: int = 1000

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return (
                value.replace("postgresql://", "postgresql+asyncpg://", 1)
                .replace("postgres://", "postgresql+asyncpg://", 1)
                .replace("sslmode=require", "ssl=require")
                .replace("channel_binding=require&", "")
                .replace("&channel_binding=require", "")
                .replace("?channel_binding=require", "?")
            )
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment in {"development", "test"}:
            return self
        if self.jwt_secret_key == "dev-only-change-me" or len(self.jwt_secret_key) < 32:
            raise ValueError("JWT_SECRET_KEY must be a random secret of at least 32 characters in production")
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE must be true in production")
        if self.jwt_algorithm != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256")
        origins = self.cors_origin_list
        if not origins or "*" in origins or any(urlparse(origin).scheme != "https" or not urlparse(origin).netloc or urlparse(origin).path not in {"", "/"} for origin in origins):
            raise ValueError("CORS_ORIGINS must contain only exact HTTPS origins in production")
        if not self.public_base_url.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL must use HTTPS in production")
        if not self.smtp_host or not self.smtp_from:
            raise ValueError("SMTP_HOST and SMTP_FROM are required in production")
        if not self.redis_url:
            raise ValueError("REDIS_URL is required in production")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
