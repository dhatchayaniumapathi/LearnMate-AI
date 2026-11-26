"""Database configuration and session management."""
import logging
from typing import AsyncGenerator, Optional
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


def create_engine_instance() -> Optional[AsyncEngine]:
    """Create async engine safely without crashing at import time if driver or config is unavailable."""
    url = settings.DATABASE_URL
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Convert PostgreSQL SSL parameters for asyncpg
    if "sslmode=require" in url:
        url = url.replace("sslmode=require", "ssl=require")

    if "channel_binding=require" in url:
        url = url.replace("&channel_binding=require", "")

    try:
        engine_args = {"echo": settings.DATABASE_ECHO}
        if "postgresql" in url:
            engine_args["pool_pre_ping"] = True
        return create_async_engine(url, **engine_args)
    except Exception as exc:
        logger.warning(f"Could not initialize database engine: {exc}")
        return None


engine = create_engine_instance()

if engine:
    async_session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
else:
    async_session_maker = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining an asynchronous database session."""
    if not async_session_maker:
        raise RuntimeError("Database engine is not initialized. Please verify DATABASE_URL.")
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_health() -> bool:
    """Check connectivity to the configured database with safe failure handling."""
    if not engine:
        return False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.debug(f"Database health check unreached (expected in offline local test mode): {exc}")
        return False
