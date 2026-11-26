"""Security utilities for password hashing, opaque tokens, and JWT management."""
import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Argon2 Password Hasher with recommended settings
_password_hasher = PasswordHasher()


# ==============================================================================
# Security Exceptions
# ==============================================================================

class SecurityError(Exception):
    """Base exception for authentication and token validation errors."""
    pass


class TokenExpiredError(SecurityError):
    """Raised when an access token has expired."""
    pass


class TokenInvalidError(SecurityError):
    """Raised when a token signature, issuer, audience, or claim validation fails."""
    pass


# ==============================================================================
# Password Hashing & Verification (Argon2)
# ==============================================================================

def get_password_hash(password: str) -> str:
    """Hash a plaintext password using Argon2."""
    if not password:
        raise ValueError("Password cannot be empty.")
    return _password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash.

    Safely returns False on mismatch, invalid hash formatting, or corrupt inputs.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as exc:
        logger.warning(f"Unexpected error during password verification: {exc}")
        return False


def check_needs_rehash(hashed_password: str) -> bool:
    """Check if the hash requires updating to newer Argon2 parameters."""
    try:
        return _password_hasher.check_needs_rehash(hashed_password)
    except Exception:
        return True


# ==============================================================================
# Opaque Refresh Token Generation & Hashing
# ==============================================================================

def generate_opaque_token(nbytes: int = 64) -> str:
    """Generate a cryptographically secure, URL-safe random string for refresh tokens."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Compute the SHA-256 hexadecimal digest of an opaque token string.

    Only this 64-character hash is persisted in the database.
    """
    if not token:
        raise ValueError("Token string cannot be empty.")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ==============================================================================
# JWT Access Token Generation & Strict Claim Validation
# ==============================================================================

def create_access_token(
    subject: Union[str, uuid.UUID],
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token with all required security claims.

    Mandatory claims included:
      - sub: Subject identifier (user UUID)
      - exp: Expiration timestamp (UTC)
      - iat: Issued-at timestamp (UTC)
      - jti: Unique token identifier (UUID4)
      - iss: Token issuer (from settings)
      - aud: Token audience (from settings)
      - token_type: Literal string "access"
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "token_type": "access",
    }

    if additional_claims:
        reserved_keys = {"sub", "exp", "iat", "jti", "iss", "aud", "token_type"}
        filtered_claims = {
            k: v for k, v in additional_claims.items() if k not in reserved_keys
        }
        payload.update(filtered_claims)

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and strictly validate access token claims.

    Enforces expiration, issued-at, issuer, audience, and token_type='access'.
    Raises TokenExpiredError or TokenInvalidError on validation failures.
    """
    if not token:
        raise TokenInvalidError("Token string cannot be empty.")

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={
                "require": ["sub", "exp", "iat", "jti", "iss", "aud"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_iss": True,
                "verify_aud": True,
            },
        )

        if payload.get("token_type") != "access":
            raise TokenInvalidError("Invalid token type claim: expected 'access'")

        return payload

    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError("Access token has expired.") from exc
    except (jwt.InvalidTokenError, jwt.PyJWTError) as exc:
        raise TokenInvalidError(f"Token validation failed: {str(exc)}") from exc
