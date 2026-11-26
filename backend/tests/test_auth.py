"""Comprehensive authentication, token lifecycle, and security test suite."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, generate_opaque_token, hash_token
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User

pytestmark = pytest.mark.anyio

# Helper for trusted Origin header
TRUSTED_ORIGIN_HEADER = {"Origin": "http://localhost:5173"}
UNTRUSTED_ORIGIN_HEADER = {"Origin": "http://attacker-site.com"}


# ==============================================================================
# 1. Registration Test Suite
# ==============================================================================

async def test_register_user_success(async_client: AsyncClient, db_session: AsyncSession):
    """Verify standard user registration succeeds with 201 status and valid schema."""
    payload = {
        "name": "Jane Student",
        "email": "jane.student@university.edu",
        "password": "ValidPassword123!",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Jane Student"
    assert data["email"] == "jane.student@university.edu"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data


async def test_register_duplicate_email(async_client: AsyncClient):
    """Verify duplicate email registration is rejected with 400 Bad Request."""
    payload = {
        "name": "Original User",
        "email": "duplicate@university.edu",
        "password": "Password123!",
    }
    first_res = await async_client.post("/api/v1/auth/register", json=payload)
    assert first_res.status_code == 201

    # Attempt registration with casing/whitespace variant
    dup_payload = {
        "name": "Second User",
        "email": "  DUPLICATE@university.edu ",
        "password": "AnotherPassword123!",
    }
    dup_res = await async_client.post("/api/v1/auth/register", json=dup_payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"].lower()


async def test_register_invalid_email(async_client: AsyncClient):
    """Verify malformed email addresses are rejected with 422 Unprocessable Entity."""
    payload = {
        "name": "Bad Email User",
        "email": "not-an-email-format",
        "password": "Password123!",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


async def test_register_short_password(async_client: AsyncClient):
    """Verify passwords shorter than 8 characters are rejected with 422."""
    payload = {
        "name": "Short Password User",
        "email": "shortpw@university.edu",
        "password": "short",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


async def test_register_whitespace_password(async_client: AsyncClient):
    """Verify whitespace-only passwords are explicitly rejected with 422."""
    payload = {
        "name": "Space Password User",
        "email": "spacess@university.edu",
        "password": "         ",
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


async def test_register_argon2_hash_stored(async_client: AsyncClient, db_session: AsyncSession):
    """Verify database stores password as an Argon2 hash, never in plaintext."""
    raw_password = "SecretArgonPassword123!"
    payload = {
        "name": "Crypto Check",
        "email": "crypto@university.edu",
        "password": raw_password,
    }
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    # Query DB directly to inspect stored hash
    stmt = select(User).where(User.email == "crypto@university.edu")
    result = await db_session.execute(stmt)
    user_record = result.scalar_one_or_none()

    assert user_record is not None
    assert user_record.hashed_password.startswith("$argon2")
    assert raw_password not in user_record.hashed_password


# ==============================================================================
# 2. Login Test Suite
# ==============================================================================

async def test_login_success(async_client: AsyncClient):
    """Verify successful authentication returns access JWT and attaches refresh cookie."""
    reg_payload = {"name": "Login User", "email": "login@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {"email": "login@university.edu", "password": "Password123!"}
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login@university.edu"

    # Verify refresh cookie
    assert "refresh_token" in response.cookies
    cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header
    assert "samesite=lax" in cookie_header.lower()
    assert "Path=/api/v1/auth" in cookie_header


async def test_login_cookie_attributes(async_client: AsyncClient):
    """Verify refresh cookie contains correct Max-Age and absolute GMT expires attribute."""
    reg_payload = {"name": "Cookie User", "email": "cookie@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {"email": "cookie@university.edu", "password": "Password123!"}
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200

    cookie_header = response.headers.get("set-cookie", "")
    expected_max_age = str(settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)
    assert f"Max-Age={expected_max_age}" in cookie_header
    assert "expires=" in cookie_header.lower()
    assert "GMT" in cookie_header


async def test_login_wrong_password(async_client: AsyncClient):
    """Verify invalid password returns generic 401 Unauthorized."""
    reg_payload = {"name": "Wrong Pw User", "email": "wrongpw@university.edu", "password": "CorrectPassword123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {"email": "wrongpw@university.edu", "password": "IncorrectPassword!"}
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "invalid email or password" in response.json()["detail"].lower()


async def test_login_unknown_email(async_client: AsyncClient):
    """Verify non-existent email returns generic 401 Unauthorized without user enumeration."""
    login_payload = {"email": "nonexistent@university.edu", "password": "Password123!"}
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "invalid email or password" in response.json()["detail"].lower()


async def test_login_inactive_account(async_client: AsyncClient, db_session: AsyncSession):
    """Verify deactivated user account cannot log in and receives 403 Forbidden."""
    reg_payload = {"name": "Inactive User", "email": "inactive@university.edu", "password": "Password123!"}
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    user_id = uuid.UUID(reg_res.json()["id"])

    # Deactivate user directly in database
    user = await db_session.get(User, user_id)
    user.is_active = False
    await db_session.commit()

    login_payload = {"email": "inactive@university.edu", "password": "Password123!"}
    response = await async_client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 403
    assert "deactivated" in response.json()["detail"].lower()


# ==============================================================================
# 3. Access Authentication (/api/v1/auth/me) Test Suite
# ==============================================================================

async def test_me_valid_jwt(async_client: AsyncClient):
    """Verify protected /me endpoint returns user profile when presenting valid access JWT."""
    reg_payload = {"name": "Me User", "email": "me@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_payload = {"email": "me@university.edu", "password": "Password123!"}
    login_res = await async_client.post("/api/v1/auth/login", json=login_payload)
    token = login_res.json()["access_token"]

    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["email"] == "me@university.edu"


async def test_me_missing_token(async_client: AsyncClient):
    """Verify /me returns 401 when Authorization header is absent."""
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_malformed_token(async_client: AsyncClient):
    """Verify /me returns 401 when Authorization header contains invalid token string."""
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert response.status_code == 401


async def test_me_expired_token(async_client: AsyncClient):
    """Verify /me returns 401 with standard error description when token is expired."""
    expired_token = create_access_token(
        subject=uuid.uuid4(),
        expires_delta=timedelta(seconds=-10),
    )
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


async def test_me_forged_signature(async_client: AsyncClient):
    """Verify /me rejects tokens signed with a different secret key."""
    fake_payload = {
        "sub": str(uuid.uuid4()),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "jti": str(uuid.uuid4()),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "token_type": "access",
    }
    forged_token = jwt.encode(fake_payload, "untrusted-forged-secret-key-32-bytes", algorithm="HS256")

    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert response.status_code == 401


async def test_me_inactive_user(async_client: AsyncClient, db_session: AsyncSession):
    """Verify user deactivated after token issuance cannot access protected endpoints."""
    reg_payload = {"name": "Later Inactive", "email": "laterinactive@university.edu", "password": "Password123!"}
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    user_id = uuid.UUID(reg_res.json()["id"])

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "laterinactive@university.edu", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]

    # Deactivate user after login
    user = await db_session.get(User, user_id)
    user.is_active = False
    await db_session.commit()

    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ==============================================================================
# 4. Refresh Token & Concurrency Test Suite
# ==============================================================================

async def test_refresh_token_rotation_success(async_client: AsyncClient):
    """Verify refresh endpoint rotates opaque token and issues fresh access JWT."""
    reg_payload = {"name": "Rotate User", "email": "rotate@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "rotate@university.edu", "password": "Password123!"},
    )
    first_refresh_cookie = login_res.cookies["refresh_token"]

    # Request rotation with trusted Origin header
    refresh_res = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": first_refresh_cookie},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data

    # Verify a new refresh cookie is emitted
    second_refresh_cookie = refresh_res.cookies["refresh_token"]
    assert second_refresh_cookie != first_refresh_cookie


async def test_refresh_token_old_token_revoked(async_client: AsyncClient):
    """Verify old refresh token cannot be used again once rotated."""
    reg_payload = {"name": "Old Token User", "email": "oldtoken@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "oldtoken@university.edu", "password": "Password123!"},
    )
    old_token = login_res.cookies["refresh_token"]

    # Perform legitimate first rotation
    first_rot_res = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": old_token},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    assert first_rot_res.status_code == 200

    # Attempt to re-use the old token -> must fail
    replay_res = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": old_token},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    assert replay_res.status_code == 401


async def test_refresh_token_reuse_family_revocation(async_client: AsyncClient):
    """Verify replaying an old token revokes the ENTIRE token family (breach mitigation)."""
    reg_payload = {"name": "Replay User", "email": "replay@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "replay@university.edu", "password": "Password123!"},
    )
    token_1 = login_res.cookies["refresh_token"]

    # Rotate 1 -> 2
    rot_res = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": token_1},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    token_2 = rot_res.cookies["refresh_token"]

    # Attacker or replay sends token_1 again!
    replay_res = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": token_1},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    assert replay_res.status_code == 401
    assert "token reuse detected" in replay_res.json()["detail"].lower()

    # Now verify that even token_2 (the newest active token) is ALSO revoked!
    subsequent_res = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": token_2},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    assert subsequent_res.status_code == 401


async def test_refresh_token_expired_isolation(async_client: AsyncClient, db_session: AsyncSession):
    """Verify expired refresh tokens are rejected without revoking other valid sessions."""
    reg_payload = {"name": "Expire User", "email": "expire@university.edu", "password": "Password123!"}
    reg_res = await async_client.post("/api/v1/auth/register", json=reg_payload)
    user_id = uuid.UUID(reg_res.json()["id"])

    # Create an artificially expired token in DB directly
    raw_expired = generate_opaque_token()
    token_hash_expired = hash_token(raw_expired)
    expired_record = RefreshToken(
        user_id=user_id,
        token_hash=token_hash_expired,
        family_id=uuid.uuid4(),
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(expired_record)

    # Create a separate, valid active token in another family
    raw_valid = generate_opaque_token()
    valid_record = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(raw_valid),
        family_id=uuid.uuid4(),
        is_revoked=False,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(valid_record)
    await db_session.commit()

    # Submit expired token -> 401
    exp_res = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": raw_expired},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    assert exp_res.status_code == 401
    assert "expired" in exp_res.json()["detail"].lower()

    # Verify the separate valid session was NOT revoked!
    await db_session.refresh(valid_record)
    assert valid_record.is_revoked is False


async def test_refresh_token_invalid(async_client: AsyncClient):
    """Verify non-existent/bogus refresh token is rejected with 401."""
    response = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "completely_bogus_token_value"},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    assert response.status_code == 401


async def test_refresh_token_concurrency_locking(async_client: AsyncClient):
    """Verify concurrent refresh calls presenting identical token cannot split into multiple chains."""
    reg_payload = {"name": "Concurrent User", "email": "concurrent@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "concurrent@university.edu", "password": "Password123!"},
    )
    shared_token = login_res.cookies["refresh_token"]

    # Dispatch 3 concurrent rotation requests with the identical token
    async def make_refresh_call():
        return await async_client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": shared_token},
            headers=TRUSTED_ORIGIN_HEADER,
        )

    results = await asyncio.gather(
        make_refresh_call(),
        make_refresh_call(),
        make_refresh_call(),
        return_exceptions=True,
    )

    statuses = [r.status_code for r in results if not isinstance(r, Exception)]
    # Exactly one request can succeed (200) or all but one rejected (401)
    assert 200 in statuses, "At least one rotation request must succeed"
    assert statuses.count(200) == 1, "Only ONE concurrent request should succeed; no split chains allowed"


# ==============================================================================
# 5. Logout Test Suite
# ==============================================================================

async def test_logout_success(async_client: AsyncClient, db_session: AsyncSession):
    """Verify logging out revokes the refresh token and clears the cookie."""
    reg_payload = {"name": "Logout User", "email": "logout@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "logout@university.edu", "password": "Password123!"},
    )
    token_val = login_res.cookies["refresh_token"]

    logout_res = await async_client.post(
        "/api/v1/auth/logout",
        cookies={"refresh_token": token_val},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out."

    # Check cookie is cleared in response
    cleared_cookie_header = logout_res.headers.get("set-cookie", "")
    assert "Max-Age=0" in cleared_cookie_header or "expires=" in cleared_cookie_header.lower()

    # Verify DB record is revoked
    target_hash = hash_token(token_val)
    stmt = select(RefreshToken).where(RefreshToken.token_hash == target_hash)
    record = (await db_session.execute(stmt)).scalar_one_or_none()
    assert record is not None
    assert record.is_revoked is True


async def test_logout_token_cannot_be_used(async_client: AsyncClient):
    """Verify logged-out refresh token cannot be used again for rotation."""
    reg_payload = {"name": "No Reuse Logout", "email": "noreuse@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "noreuse@university.edu", "password": "Password123!"},
    )
    token_val = login_res.cookies["refresh_token"]

    await async_client.post(
        "/api/v1/auth/logout",
        cookies={"refresh_token": token_val},
        headers=TRUSTED_ORIGIN_HEADER,
    )

    # Attempt to refresh with logged-out token
    refresh_attempt = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": token_val},
        headers=TRUSTED_ORIGIN_HEADER,
    )
    assert refresh_attempt.status_code == 401


# ==============================================================================
# 6. CSRF & Origin Guard Test Suite
# ==============================================================================

async def test_csrf_trusted_origin_accepted(async_client: AsyncClient):
    """Verify requests with configured CORS origins are accepted on /refresh."""
    reg_payload = {"name": "CSRF User", "email": "csrf@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "csrf@university.edu", "password": "Password123!"},
    )
    token = login_res.cookies["refresh_token"]

    response = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": token},
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 200


async def test_csrf_untrusted_origin_rejected(async_client: AsyncClient):
    """Verify cross-origin requests from untrusted origins receive 403 Forbidden."""
    response = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "some_token"},
        headers=UNTRUSTED_ORIGIN_HEADER,
    )
    assert response.status_code == 403
    assert "cross-origin request forbidden" in response.json()["detail"].lower()


async def test_csrf_missing_origin_rejected(async_client: AsyncClient):
    """Verify requests lacking Origin headers on cookie-based routes receive 403 Forbidden."""
    response = await async_client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "some_token"},
        headers={},  # Missing Origin header
    )
    assert response.status_code == 403
    assert "origin header is required" in response.json()["detail"].lower()


async def test_cookie_attributes_full_validation(async_client: AsyncClient):
    """Verify full suite of cookie security attributes on login."""
    reg_payload = {"name": "Full Cookie", "email": "fullcookie@university.edu", "password": "Password123!"}
    await async_client.post("/api/v1/auth/register", json=reg_payload)

    res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "fullcookie@university.edu", "password": "Password123!"},
    )
    cookie_str = res.headers.get("set-cookie", "")

    # Attribute checks
    assert "refresh_token=" in cookie_str
    assert "httponly" in cookie_str.lower()
    assert "samesite=lax" in cookie_str.lower()
    assert "path=/api/v1/auth" in cookie_str.lower()
    assert "max-age=" in cookie_str.lower()
    assert "expires=" in cookie_str.lower()
