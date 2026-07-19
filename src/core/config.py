from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Simple Blog API"
    app_version: str = "0.1.0"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 4000
    reload: bool = True
    log_level: str = "INFO"
    cors_origins: str = "http://127.0.0.1:4000,http://127.0.0.1:5500"
    database_url: str = "postgresql+asyncpg://blog:blog@localhost:5432/blog"
    jwt_secret_key: str = "dev-only-change-me"
    cookie_secure: bool = False
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "simple-blog-media"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
