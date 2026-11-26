"""Test suite for system health endpoints."""


def test_root_endpoint(client):
    """Verify root endpoint responds with basic platform metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "LearnMate AI API" in data["message"]
    assert "version" in data
    assert data["documentation"] == "/docs"


def test_api_v1_health_endpoint(client):
    """Verify /api/v1/health returns properly structured health check response."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "degraded"]
    assert data["service"] == "LearnMate AI API"
    assert "version" in data
    assert "timestamp" in data
    assert "database_connected" in data
    assert "components" in data
    assert "api" in data["components"]
    assert data["components"]["api"] == "healthy"
