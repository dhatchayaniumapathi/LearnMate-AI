"""Aggregated API v1 router."""
from fastapi import APIRouter
from app.api.v1.endpoints import auth, health

api_v1_router = APIRouter()

# Mount health diagnostics
api_v1_router.include_router(
    health.router,
    prefix="",
    tags=["Health"],
)

# Mount authentication endpoints
api_v1_router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"],
)
