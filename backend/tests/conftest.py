"""Pytest configuration and strict database isolation test fixtures."""
import os
from typing import AsyncGenerator, Dict
from urllib.parse import urlsplit

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, pool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import get_db
from app.db.models import Base, RefreshToken, User
from app.main import app


# ==============================================================================
# Strict Database Identity & Isolation Verification
# ==============================================================================

class DatabaseIdentityError(RuntimeError):
    """Raised when database identity verification fails or targets active database."""
    pass


def extract_database_identity(url: str) -> Dict[str, str]:
    """Parse connection URL and extract normalized identity (hostname, port, dbname).

    Normalizes Neon pooled and direct endpoints by stripping '-pooler' from hostname.
    Enforces PostgreSQL compatibility and rejects SQLite or other non-PostgreSQL schemes.
    Fails closed on missing or malformed components.
    """
    if not url or not isinstance(url, str):
        raise DatabaseIdentityError("Database URL is empty or not a valid string.")

    clean_url = url.strip()
    clean_url_no_params = clean_url.split("?")[0].split("#")[0]

    try:
        parsed = urlsplit(clean_url_no_params)
    except Exception as exc:
        raise DatabaseIdentityError(f"Malformed database URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()

    # Reject SQLite explicitly
    if scheme == "sqlite" or scheme.startswith("sqlite+"):
        raise DatabaseIdentityError(
            "SQLite is not supported for this test suite. "
            "This authentication concurrency suite must use PostgreSQL."
        )

    # Validate PostgreSQL-compatible scheme
    allowed_schemes = {
        "postgresql",
        "postgres",
        "postgresql+asyncpg",
        "postgresql+psycopg",
        "postgresql+psycopg2",
    }
    if scheme not in allowed_schemes:
        raise DatabaseIdentityError(
            f"Unsupported or unrecognized database URL scheme: '{scheme}'. "
            "A PostgreSQL-compatible scheme (postgresql://, postgres://, or postgresql+asyncpg://) is required."
        )

    # Extract and validate hostname
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise DatabaseIdentityError("Malformed database URL: hostname is missing.")

    # Normalize Neon hostnames: strip '-pooler.' to detect direct vs pooled endpoint collision
    # e.g., 'ep-xyz-123456-pooler.c-5.ap-southeast-1.aws.neon.tech' -> 'ep-xyz-123456.c-5.ap-southeast-1.aws.neon.tech'
    normalized_hostname = hostname.replace("-pooler.", ".")

    # Extract and validate port (PostgreSQL default: 5432)
    try:
        raw_port = parsed.port
    except ValueError as exc:
        raise DatabaseIdentityError(f"Malformed database URL: invalid port specification ({exc}).") from exc

    if raw_port is None:
        port = 5432
    else:
        if not (1 <= raw_port <= 65535):
            raise DatabaseIdentityError(
                f"Malformed database URL: port {raw_port} is out of valid range (1-65535)."
            )
        port = raw_port

    # Extract database name from path
    database_name = parsed.path.strip("/").strip().lower()
    if not database_name:
        raise DatabaseIdentityError("Malformed database URL: database name is missing.")

    return {
        "host": normalized_hostname,
        "port": str(port),
        "database": database_name,
    }


def assert_is_safe_test_database(test_url: str) -> None:
    """Strictly assert test database does not collide with active application databases.

    Compares normalized hostname, port, and database name against BOTH
    settings.DATABASE_URL and settings.DIRECT_DATABASE_URL.

    Requirements:
    1. DATABASE_URL must be present and parse successfully.
    2. DIRECT_DATABASE_URL must also be present and parse successfully.
    3. Fails closed with DatabaseIdentityError if either active URL is missing,
       fails to parse, or if TEST_DATABASE_URL matches either active database identity.
    """
    test_identity = extract_database_identity(test_url)

    # 1. Require and parse active DATABASE_URL
    app_db_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    if not app_db_url or not isinstance(app_db_url, str) or not app_db_url.strip():
        raise DatabaseIdentityError(
            "[SAFETY HALT] Active DATABASE_URL is missing or empty. "
            "Both DATABASE_URL and DIRECT_DATABASE_URL must be present to verify test database isolation."
        )
    try:
        app_identity = extract_database_identity(app_db_url)
    except DatabaseIdentityError:
        raise
    except Exception as exc:
        raise DatabaseIdentityError(f"Failed to parse active DATABASE_URL: {exc}") from exc

    # 2. Require and parse active DIRECT_DATABASE_URL
    direct_db_url = os.getenv("DIRECT_DATABASE_URL") or settings.DIRECT_DATABASE_URL
    if not direct_db_url or not isinstance(direct_db_url, str) or not direct_db_url.strip():
        raise DatabaseIdentityError(
            "[SAFETY HALT] Active DIRECT_DATABASE_URL is missing or empty. "
            "Both DATABASE_URL and DIRECT_DATABASE_URL must be present to verify test database isolation."
        )
    try:
        direct_identity = extract_database_identity(direct_db_url)
    except DatabaseIdentityError:
        raise
    except Exception as exc:
        raise DatabaseIdentityError(f"Failed to parse active DIRECT_DATABASE_URL: {exc}") from exc

    # 3. Compare against active DATABASE_URL
    if (
        test_identity["host"] == app_identity["host"]
        and test_identity["port"] == app_identity["port"]
        and test_identity["database"] == app_identity["database"]
    ):
        raise DatabaseIdentityError(
            f"\n[SECURITY HALT] TEST_DATABASE_URL targets the active application database!\n"
            f"Target host: '{test_identity['host']}' | Port: '{test_identity['port']}' | Database: '{test_identity['database']}'\n"
            "Execution aborted to prevent data loss or schema contamination on the active database.\n"
        )

    # 4. Compare against active DIRECT_DATABASE_URL
    if (
        test_identity["host"] == direct_identity["host"]
        and test_identity["port"] == direct_identity["port"]
        and test_identity["database"] == direct_identity["database"]
    ):
        raise DatabaseIdentityError(
            f"\n[SECURITY HALT] TEST_DATABASE_URL targets the active DIRECT_DATABASE_URL endpoint!\n"
            f"Target host: '{test_identity['host']}' | Port: '{test_identity['port']}' | Database: '{test_identity['database']}'\n"
            "Execution aborted to prevent data loss or schema contamination on the direct database.\n"
        )


def get_isolated_test_db_url() -> str:
    """Validate and retrieve isolated TEST_DATABASE_URL with fail-closed safety checks."""
    test_url = os.getenv("TEST_DATABASE_URL") or settings.TEST_DATABASE_URL
    if not test_url:
        pytest.exit(
            "\n[SAFETY HALT] TEST_DATABASE_URL is not set in environment or backend/.env.\n"
            "To protect the active Neon database, tests are strictly prevented from running.\n"
            "Please configure TEST_DATABASE_URL to point to a separate isolated test database.\n",
            returncode=1,
        )

    # Execute strict collision verification against both application URLs
    try:
        assert_is_safe_test_database(test_url)
    except DatabaseIdentityError as err:
        pytest.exit(f"\n{str(err)}", returncode=1)

    # Convert to asyncpg driver scheme for PostgreSQL
    url = test_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "sslmode=require" in url:
        url = url.replace("sslmode=require", "ssl=require")
    if "channel_binding=require" in url:
        url = url.replace("&channel_binding=require", "")

    return url


# Initialize isolated test engine
_test_db_url = get_isolated_test_db_url()
test_engine = create_async_engine(
    _test_db_url,
    poolclass=pool.NullPool,
    echo=False,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ==============================================================================
# Pytest Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def anyio_backend():
    """Configure anyio runner for pytest."""
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
async def initialize_test_database():
    """Create schema tables on the isolated test database once per test session.

    Guarantees:
    - Verifies test database safety immediately before create_all().
    - Verifies test database safety immediately before drop_all().
    - Teardown safety checks cannot be bypassed even if setup or tests fail.
    """
    # 1. Pre-creation safety verification
    assert_is_safe_test_database(_test_db_url)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        # 2. Pre-teardown safety verification
        assert_is_safe_test_database(_test_db_url)
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()


@pytest.fixture(autouse=True)
async def clean_database():
    """Clean table rows between individual test cases to ensure strict test isolation.

    Deletes child records (RefreshToken) before parent records (User) to respect foreign keys.
    """
    yield
    async with TestingSessionLocal() as session:
        try:
            await session.execute(delete(RefreshToken))
            await session.execute(delete(User))
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(autouse=True)
def override_db_dependency():
    """Override FastAPI get_db dependency to direct all API requests to the isolated test DB."""
    async def _test_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestingSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()

    try:
        app.dependency_overrides[get_db] = _test_get_db
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a direct async session connected to the isolated test database."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Asynchronous HTTP test client bound to FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
