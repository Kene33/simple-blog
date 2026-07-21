from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Simple Blog API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
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
    cookie_secure: bool = False
    cookie_domain: str | None = None
    public_base_url: str = "http://localhost:4000"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "simple-blog-media"
    s3_access_key: str = "minio"
    s3_secret_key: str = "minio-password"
    s3_region: str = "us-east-1"

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
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
