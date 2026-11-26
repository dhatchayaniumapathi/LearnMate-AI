"""Authentication API endpoints."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.db.models.user import User
from app.schemas.auth import (
    MessageResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services import auth_service
from app.services.auth_service import (
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenExpiredError,
    TokenReuseDetectedError,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Cookie constants
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = f"{settings.API_V1_STR}/auth"


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Attach rotating opaque refresh token as secure HttpOnly cookie."""
    max_age_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    expires_dt = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    is_production = settings.ENVIRONMENT.lower() == "production"

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        max_age=max_age_seconds,
        expires=expires_dt,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=is_production,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear refresh token cookie upon logout, expiration, or revocation."""
    is_production = settings.ENVIRONMENT.lower() == "production"

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="lax",
        secure=is_production,
    )


def _verify_trusted_origin(request: Request) -> None:
    """Validate Origin header against settings.CORS_ORIGINS for cookie-based auth endpoints.

    Raises:
        HTTPException 403: If Origin header is missing or does not match configured CORS origins.
    """
    origin = request.headers.get("origin")
    if not origin:
        logger.warning("Rejected cookie-based auth request: missing Origin header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin header is required for cookie-based authentication requests.",
        )

    allowed_origins = (
        settings.CORS_ORIGINS
        if isinstance(settings.CORS_ORIGINS, list)
        else [settings.CORS_ORIGINS]
    )
    # Disallow wildcard origins and normalize trailing slashes
    normalized_origin = origin.rstrip("/")
    normalized_allowed = {
        o.rstrip("/") for o in allowed_origins if o and o != "*"
    }

    if normalized_origin not in normalized_allowed:
        logger.warning(f"Rejected cookie-based auth request: untrusted origin '{origin}'.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin request forbidden.",
        )


# ==============================================================================
# Auth Routes
# ==============================================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account",
    description="Registers a new user, hashes password with Argon2, and stores normalized profile.",
)
async def register(
    user_in: UserRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Register student user account."""
    try:
        user = await auth_service.register_user(db, user_in)
        return UserResponse.model_validate(user)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        ) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and establish session",
    description="Validates credentials, emits short-lived access JWT, and attaches rotating HttpOnly refresh cookie.",
)
async def login(
    credentials: UserLoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate student user and issue access JWT + refresh cookie."""
    try:
        user = await auth_service.authenticate_user(
            db=db,
            email=credentials.email,
            password=credentials.password,
        )
        access_token, raw_refresh_token, _ = await auth_service.create_user_session(
            db=db,
            user=user,
        )
        _set_refresh_cookie(response, raw_refresh_token)

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        ) from exc


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access JWT",
    description="Reads HttpOnly refresh cookie, performs transactional rotation with row-level locking, and updates cookie.",
)
async def refresh_token(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Rotate refresh token and issue new access JWT."""
    _verify_trusted_origin(request)
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if not raw_token:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        new_access_token, new_raw_token, user = await auth_service.rotate_refresh_token(
            db=db,
            raw_token=raw_token,
        )
        _set_refresh_cookie(response, new_raw_token)

        return TokenResponse(
            access_token=new_access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )
    except TokenReuseDetectedError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Security violation: Token reuse detected. All sessions terminated.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except RefreshTokenExpiredError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except (InvalidRefreshTokenError, InactiveUserError) as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Terminate authenticated session",
    description="Revokes current refresh token record in database and deletes HttpOnly refresh cookie.",
)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Log out user by revoking refresh token and clearing cookie."""
    _verify_trusted_origin(request)
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_token:
        await auth_service.revoke_user_session(db=db, raw_token=raw_token)

    _clear_refresh_cookie(response)
    return MessageResponse(message="Successfully logged out.")


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current user profile",
    description="Protected endpoint requiring valid Bearer access token. Returns profile without secrets.",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Return authenticated student profile."""
    return UserResponse.model_validate(current_user)
