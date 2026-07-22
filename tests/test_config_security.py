import pytest
from fastapi import Request
from pydantic import ValidationError

from src.core.config import Settings
from src.core.errors import AppError
from src.modules.auth.dependencies import _validate_request_origin


def test_production_requires_secure_cookie_and_strong_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", cookie_secure=False)
    settings = Settings(environment="production", cookie_secure=True, jwt_secret_key="a" * 32, cors_origins="https://app.example.com", public_base_url="https://app.example.com", smtp_host="smtp.example.com", smtp_from="noreply@example.com", redis_url="redis://localhost:6379/0")
    assert settings.cookie_secure is True


def test_production_request_origin_policy() -> None:
    settings = Settings(environment="production", cookie_secure=True, jwt_secret_key="a" * 32, cors_origins="https://app.example.com", public_base_url="https://app.example.com", smtp_host="smtp.example.com", smtp_from="noreply@example.com", redis_url="redis://localhost:6379/0")

    def request(headers: list[tuple[bytes, bytes]]) -> Request:
        return Request({"type": "http", "method": "POST", "path": "/api/v1/posts", "headers": headers})

    _validate_request_origin(request([(b"origin", b"https://app.example.com")]), settings)
    _validate_request_origin(request([(b"referer", b"https://app.example.com/posts/1")]), settings)
    with pytest.raises(AppError, match="Request origin is not allowed"):
        _validate_request_origin(request([(b"origin", b"https://evil.example")]), settings)
    with pytest.raises(AppError, match="Request origin is not allowed"):
        _validate_request_origin(request([]), settings)
