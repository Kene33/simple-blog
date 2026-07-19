import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from src.core.config import Settings

password_hash = PasswordHash.recommended()


@dataclass(frozen=True)
class TokenData:
    value: str
    expires_at: datetime


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(settings: Settings, user_id: uuid.UUID, session_id: uuid.UUID, csrf_token: str) -> TokenData:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": str(user_id), "sid": str(session_id), "csrf": csrf_token, "type": "access", "exp": expires_at}
    return TokenData(jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), expires_at)


def create_refresh_token(settings: Settings, user_id: uuid.UUID, session_id: uuid.UUID) -> TokenData:
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_days)
    payload = {"sub": str(user_id), "sid": str(session_id), "type": "refresh", "exp": expires_at}
    return TokenData(jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), expires_at)


def decode_token(settings: Settings, token: str, token_type: str) -> dict[str, str]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise ValueError("Invalid token") from exc
    if payload.get("type") != token_type:
        raise ValueError("Invalid token type")
    return payload
