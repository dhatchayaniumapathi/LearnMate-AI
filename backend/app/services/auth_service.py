"""Authentication and token session lifecycle management service."""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    get_password_hash,
    hash_token,
    verify_password,
)
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.schemas.auth import UserRegisterRequest

logger = logging.getLogger(__name__)


# ==============================================================================
# Domain Exceptions
# ==============================================================================

class AuthServiceError(Exception):
    """Base exception for all authentication service errors."""
    pass


class EmailAlreadyExistsError(AuthServiceError):
    """Raised when registering an email address that is already in use."""
    pass


class InvalidCredentialsError(AuthServiceError):
    """Raised when authentication credentials (email/password) are incorrect."""
    pass


class InactiveUserError(AuthServiceError):
    """Raised when an authenticated user account is deactivated."""
    pass


class InvalidRefreshTokenError(AuthServiceError):
    """Raised when a refresh token does not exist or is malformed."""
    pass


class RefreshTokenExpiredError(AuthServiceError):
    """Raised when a refresh token has passed its expiration timestamp."""
    pass


class TokenReuseDetectedError(AuthServiceError):
    """Raised when a previously consumed or revoked refresh token is re-submitted."""
    pass


# ==============================================================================
# Helper Functions
# ==============================================================================

def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime object is timezone-aware and set to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ==============================================================================
# Service Functions
# ==============================================================================

async def register_user(db: AsyncSession, user_in: UserRegisterRequest) -> User:
    """Register a new student user, ensuring normalized email uniqueness and Argon2 hashing.

    Args:
        db: Active async database session.
        user_in: Validated registration payload.

    Returns:
        The newly persisted User ORM instance.

    Raises:
        EmailAlreadyExistsError: If email is already registered.
    """
    normalized_email = user_in.email.strip().lower()

    # Pre-check email uniqueness
    stmt = select(User).where(func.lower(User.email) == normalized_email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        logger.info("Registration rejected: duplicate email attempt.")
        raise EmailAlreadyExistsError(f"Email '{normalized_email}' is already registered.")

    hashed_pw = get_password_hash(user_in.password)

    user = User(
        email=normalized_email,
        name=user_in.name,
        hashed_password=hashed_pw,
        is_active=True,
    )
    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
        logger.info(f"User successfully registered with ID: {user.id}")
        return user
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("Database integrity error during registration commit.")
        raise EmailAlreadyExistsError(f"Email '{normalized_email}' is already registered.") from exc
    except Exception as exc:
        await db.rollback()
        logger.error(f"Unexpected error during user registration: {exc}")
        raise


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    """Authenticate a user by email and password.

    Args:
        db: Active async database session.
        email: Plaintext email address.
        password: Plaintext candidate password.

    Returns:
        The authenticated User ORM instance.

    Raises:
        InvalidCredentialsError: If user is not found or password does not match.
        InactiveUserError: If user account is marked inactive.
    """
    normalized_email = email.strip().lower()

    stmt = select(User).where(func.lower(User.email) == normalized_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        logger.info("Authentication failed: user email not found.")
        raise InvalidCredentialsError("Invalid email or password.")

    if not verify_password(password, user.hashed_password):
        logger.info(f"Authentication failed: invalid password for user ID: {user.id}")
        raise InvalidCredentialsError("Invalid email or password.")

    if not user.is_active:
        logger.warning(f"Authentication rejected: user account {user.id} is deactivated.")
        raise InactiveUserError("Your account has been deactivated. Please contact support.")

    logger.info(f"Authentication successful for user ID: {user.id}")
    return user


async def create_user_session(
    db: AsyncSession,
    user: User,
) -> Tuple[str, str, RefreshToken]:
    """Initialize a new authenticated session for a user.

    Generates a short-lived access JWT and an opaque refresh token in memory first.
    Persists only the SHA-256 hash of the refresh token with a new token family ID.
    Enforces transaction rollback on failure.

    Args:
        db: Active async database session.
        user: Authenticated User entity.

    Returns:
        Tuple of (access_token, raw_refresh_token, RefreshToken record).
    """
    # 1. Generate tokens and claims in-memory first
    access_token = create_access_token(subject=user.id)
    raw_refresh_token = generate_opaque_token()
    token_hash = hash_token(raw_refresh_token)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    family_id = uuid.uuid4()

    token_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        family_id=family_id,
        is_revoked=False,
        expires_at=expires_at,
    )
    db.add(token_record)

    try:
        await db.commit()
        await db.refresh(token_record)
        logger.info(f"Session initialized for user {user.id} under token family {family_id}")
        return access_token, raw_refresh_token, token_record
    except Exception as exc:
        await db.rollback()
        logger.error(f"Failed to persist user session for user {user.id}: {exc}")
        raise


async def rotate_refresh_token(
    db: AsyncSession,
    raw_token: str,
) -> Tuple[str, str, User]:
    """Execute transactional refresh token rotation with row-level locking.

    Order of operations:
    1. Locks the matching database row (SELECT ... FOR UPDATE).
    2. Checks expiration FIRST (expired tokens do not trigger family-wide breach revocation).
    3. Checks revocation status SECOND (revoked tokens indicate replay attacks).
    4. Generates all new tokens in memory BEFORE committing database mutations.
    5. Atomically revokes old token and stores new token in the same family.
    6. Ensures proper rollback on unexpected failures.

    Args:
        db: Active async database session.
        raw_token: Plaintext opaque refresh token received from client cookie.

    Returns:
        Tuple of (new_access_token, new_raw_refresh_token, User).

    Raises:
        InvalidRefreshTokenError: Token not found in database.
        RefreshTokenExpiredError: Token has passed expiration date.
        TokenReuseDetectedError: Revoked token presented (breach mitigation).
        InactiveUserError: User account deactivated.
    """
    if not raw_token:
        raise InvalidRefreshTokenError("Refresh token missing or empty.")

    incoming_hash = hash_token(raw_token)

    try:
        # 1. Acquire row-level lock on the refresh token row
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.token_hash == incoming_hash)
            .with_for_update()
        )
        result = await db.execute(stmt)
        existing_token = result.scalar_one_or_none()

        if not existing_token:
            logger.warning("Refresh token rotation failed: token hash not found in database.")
            raise InvalidRefreshTokenError("Invalid refresh token.")

        # 2. Check token expiration FIRST
        now = datetime.now(timezone.utc)
        token_exp = _ensure_utc(existing_token.expires_at)

        if token_exp <= now:
            logger.info(f"Refresh token {existing_token.id} has expired.")
            # Do NOT mark as revoked - expired tokens are already unusable by timestamp.
            raise RefreshTokenExpiredError("Refresh token has expired. Please log in again.")

        # 3. Check for token reuse / replay attacks SECOND
        if existing_token.is_revoked:
            logger.error(
                f"SECURITY ALERT: Refresh token reuse detected for family {existing_token.family_id}. "
                f"Revoking all tokens in this family."
            )
            # Revoke entire token family and commit immediately before raising
            revoke_family_stmt = (
                update(RefreshToken)
                .where(RefreshToken.family_id == existing_token.family_id)
                .values(is_revoked=True)
            )
            await db.execute(revoke_family_stmt)
            await db.commit()
            raise TokenReuseDetectedError(
                "Security violation: Refresh token reuse detected. All sessions in this family have been revoked."
            )

        # 4. Fetch and verify user account status
        user = await db.get(User, existing_token.user_id)
        if not user:
            existing_token.is_revoked = True
            await db.commit()
            raise InvalidRefreshTokenError("User account associated with token was not found.")

        if not user.is_active:
            existing_token.is_revoked = True
            await db.commit()
            logger.warning(f"Refresh attempted for inactive user: {user.id}")
            raise InactiveUserError("Your account has been deactivated.")

        # 5. Generate ALL new tokens in memory BEFORE modifying and committing DB
        new_raw_token = generate_opaque_token()
        new_hash = hash_token(new_raw_token)
        new_access_token = create_access_token(subject=user.id)
        new_expires_at = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        # 6. Execute atomic rotation in the database
        existing_token.is_revoked = True

        new_token_record = RefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            family_id=existing_token.family_id,
            is_revoked=False,
            expires_at=new_expires_at,
        )
        db.add(new_token_record)

        await db.commit()
        await db.refresh(new_token_record)

        logger.info(f"Token successfully rotated for user {user.id} in family {existing_token.family_id}")
        return new_access_token, new_raw_token, user

    except AuthServiceError:
        # Domain exceptions handle their own state / read-only flows
        raise
    except Exception as exc:
        await db.rollback()
        logger.error(f"Unexpected error during refresh token rotation: {exc}")
        raise


async def revoke_user_session(db: AsyncSession, raw_token: str) -> bool:
    """Revoke a single refresh token session with row-level locking and rollback guard."""
    if not raw_token:
        return False

    target_hash = hash_token(raw_token)

    try:
        stmt = (
            select(RefreshToken)
            .where(RefreshToken.token_hash == target_hash)
            .with_for_update()
        )
        result = await db.execute(stmt)
        token_record = result.scalar_one_or_none()

        if not token_record:
            return False

        if not token_record.is_revoked:
            token_record.is_revoked = True
            await db.commit()
            logger.info(f"Session {token_record.id} successfully revoked.")

        return True
    except Exception as exc:
        await db.rollback()
        logger.error(f"Error during refresh token revocation: {exc}")
        raise


async def revoke_all_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Revoke all active refresh tokens for a user with rollback guard."""
    try:
        stmt = (
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked.is_(False),
            )
            .values(is_revoked=True)
        )
        result = await db.execute(stmt)
        await db.commit()
        revoked_count = result.rowcount  # type: ignore
        logger.info(f"Revoked {revoked_count} active sessions for user {user_id}")
        return revoked_count
    except Exception as exc:
        await db.rollback()
        logger.error(f"Error revoking all sessions for user {user_id}: {exc}")
        raise
