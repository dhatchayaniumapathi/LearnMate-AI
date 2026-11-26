"""Health check response schemas."""
from datetime import datetime
from typing import Dict
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """System health check model."""
    status: str = Field(..., description="Overall system status ('ok' or 'degraded')")
    service: str = Field("LearnMate AI API", description="Service identifier")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Deployment environment")
    timestamp: datetime = Field(..., description="Server current timestamp in UTC")
    database_connected: bool = Field(..., description="Whether the primary database is reachable")
    components: Dict[str, str] = Field(
        default_factory=dict,
        description="Health status of individual system components",
    )
