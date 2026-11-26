"""FastAPI application dependencies."""
import logging
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import TokenExpiredError, TokenInvalidError, decode_access_token
from app.db.models.user import User

logger = logging.getLogger(__name__)

# OAuth2 bearer token extractor pointing to versioned auth login endpoint
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=True,
)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """Validate JWT access token and retrieve current active user.

    Raises:
        HTTPException 401: If token is expired, signature is invalid, or user does not exist.
        HTTPException 403: If user account has been deactivated.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id_str: str = payload.get("sub", "")
        if not user_id_str:
            raise credentials_exception
        user_id = uuid.UUID(user_id_str)
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="The token has expired"'},
        )
    except (TokenInvalidError, ValueError):
        raise credentials_exception

    user = await db.get(User, user_id)
    if not user:
        logger.info(f"Token validation failed: user {user_id} not found in database.")
        raise credentials_exception

    if not user.is_active:
        logger.warning(f"Access rejected: user account {user.id} is inactive.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated.",
        )

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Convenience dependency returning verified active user."""
    return current_user
