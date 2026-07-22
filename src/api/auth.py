import logging

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings, get_settings
from src.core.email import send_password_reset_email
from src.core.errors import AppError
from src.core.security import new_csrf_token
from src.db.session import get_session
from src.modules.auth.dependencies import CurrentAuth, require_csrf
from src.modules.auth.schemas import LoginRequest, PasswordResetConfirmRequest, PasswordResetRequest, PasswordResetRequestRead, RegisterRequest, SessionRead
from src.modules.auth.service import (
    AuthSession,
    RefreshReplayDetected,
    authenticate_user,
    create_password_reset,
    create_session,
    register_user,
    reset_password,
    revoke_session,
    rotate_session,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def set_session_cookies(response: Response, settings: Settings, auth_session: AuthSession) -> None:
    common = {"secure": settings.cookie_secure, "samesite": settings.cookie_samesite, "domain": settings.cookie_domain, "path": "/"}
    response.set_cookie(settings.access_cookie_name, auth_session.access.value, httponly=True, max_age=settings.access_token_minutes * 60, **common)
    response.set_cookie(settings.refresh_cookie_name, auth_session.refresh.value, httponly=True, max_age=settings.refresh_token_days * 24 * 60 * 60, **common)
    response.set_cookie(settings.csrf_cookie_name, auth_session.csrf_token, httponly=False, max_age=settings.refresh_token_days * 24 * 60 * 60, **common)


def clear_session_cookies(response: Response, settings: Settings) -> None:
    for cookie_name in (settings.access_cookie_name, settings.refresh_cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(cookie_name, domain=settings.cookie_domain, path="/", secure=settings.cookie_secure, samesite=settings.cookie_samesite)


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=SessionRead)
async def register(payload: RegisterRequest, request: Request, response: Response, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> SessionRead:
    await request.app.state.rate_limiter.check(request, "register", 5, 3600)
    try:
        user = await register_user(session, payload)
        auth_session = await create_session(session, settings, user, new_csrf_token())
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise AppError("RESOURCE_CONFLICT", "Username or email is already in use", 409) from None
    set_session_cookies(response, settings, auth_session)
    return auth_session.response


@router.post("/login", response_model=SessionRead)
async def login(payload: LoginRequest, request: Request, response: Response, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> SessionRead:
    await request.app.state.rate_limiter.check(request, "login", 30, 900)
    await request.app.state.rate_limiter.check(request, "login", 10, 900, payload.identifier.casefold())
    user = await authenticate_user(session, payload)
    auth_session = await create_session(session, settings, user, new_csrf_token())
    await session.commit()
    set_session_cookies(response, settings, auth_session)
    return auth_session.response


@router.post("/refresh", response_model=SessionRead)
async def refresh(request: Request, response: Response, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> SessionRead:
    refresh_value = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_value:
        raise AppError("AUTH_REQUIRED", "Authentication is required", 401)
    try:
        auth_session = await rotate_session(session, settings, refresh_value, request.headers.get(settings.csrf_header_name), request.cookies.get(settings.csrf_cookie_name), new_csrf_token())
        await session.commit()
    except RefreshReplayDetected as exc:
        await session.commit()
        raise AppError(exc.code, exc.message, exc.status_code) from None
    set_session_cookies(response, settings, auth_session)
    return auth_session.response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def logout(auth: CurrentAuth = Depends(require_csrf), session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> Response:
    await revoke_session(session, auth.session_id, auth.user.id)
    await session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session_cookies(response, settings)
    return response


@router.post("/password-reset/request", response_model=PasswordResetRequestRead)
async def request_password_reset(payload: PasswordResetRequest, request: Request, session: AsyncSession = Depends(get_session), settings: Settings = Depends(get_settings)) -> PasswordResetRequestRead:
    await request.app.state.rate_limiter.check(request, "password-reset-request", 5, 900, str(payload.email).casefold())
    token = await create_password_reset(session, settings, str(payload.email))
    if token:
        try:
            await send_password_reset_email(settings, str(payload.email), token)
        except Exception:
            await session.rollback()
            logger.exception("Password reset email delivery failed")
            return PasswordResetRequestRead(message="If the email is registered, a reset link has been sent.")
    await session.commit()
    return PasswordResetRequestRead(message="If the email is registered, a reset link has been sent.")


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def confirm_password_reset(payload: PasswordResetConfirmRequest, request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    await request.app.state.rate_limiter.check(request, "password-reset-confirm", 10, 900)
    await reset_password(session, payload)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
