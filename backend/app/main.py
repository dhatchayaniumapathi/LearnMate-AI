"""FastAPI main application entry point."""
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import check_database_health
from app.api.v1.router import api_v1_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Advanced AI-powered personalized learning platform for college students.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
async def root():
    """Root welcoming endpoint with platform info and docs pointers."""
    return {
        "message": "Welcome to LearnMate AI API",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "documentation": "/docs",
        "health_check": f"{settings.API_V1_STR}/health",
    }


@app.get("/health", tags=["Root"], include_in_schema=False)
async def direct_health():
    """Convenience redirect/alias to primary health check."""
    db_healthy = await check_database_health()
    return {
        "status": "ok" if db_healthy else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database_connected": db_healthy,
    }
