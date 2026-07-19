import pytest
from pydantic import ValidationError

from src.core.config import Settings


def test_production_requires_secure_cookie_and_strong_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production", cookie_secure=False)
    settings = Settings(environment="production", cookie_secure=True, jwt_secret_key="a" * 32)
    assert settings.cookie_secure is True
