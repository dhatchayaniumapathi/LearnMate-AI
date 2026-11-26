"""Health check endpoint definition."""
from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import settings
from app.core.database import check_database_health
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health & Diagnostic Check",
    description="Returns API status, database reachability, and active service flags.",
)
async def get_health() -> HealthResponse:
    db_healthy = await check_database_health()
    status = "ok" if db_healthy else "degraded"

    # Identify configured LLM providers without revealing keys
    llm_status = "configured" if any([
        settings.GEMINI_API_KEY,
        settings.GROQ_API_KEY,
        settings.ANTHROPIC_API_KEY,
        settings.OPENAI_API_KEY,
    ]) else "optional_keys_empty"

    return HealthResponse(
        status=status,
        service=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
        database_connected=db_healthy,
        components={
            "api": "healthy",
            "database": "connected" if db_healthy else "unreachable_or_uninitialized",
            "llm_gateway": llm_status,
        },
    )
