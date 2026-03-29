"""Tests for API versioning and health check endpoint.

Step 1 of Phase 1 hardening: All routes under /api/v1/, health check at /health.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from whati8.api.app import create_app


@pytest.fixture
def app():
    """Create a fresh app instance for versioning tests."""
    return create_app()


@pytest.fixture
async def raw_client(app):
    """HTTP client WITHOUT base_url prefix — tests absolute paths."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ── Health Check ──────────────────────────────────────────────


class TestHealthCheck:
    """Health check endpoint at /health (outside versioned prefix)."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, raw_client):
        """GET /health returns 200 with status, db, version fields."""
        response = await raw_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "db" in data
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, raw_client):
        """Health check does not require authentication."""
        response = await raw_client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_includes_version_string(self, raw_client):
        """Version should be a non-empty string."""
        response = await raw_client.get("/health")
        data = response.json()
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0


# ── API Versioning ────────────────────────────────────────────


class TestAPIVersioning:
    """All API routes live under /api/v1/ prefix."""

    @pytest.mark.asyncio
    async def test_auth_login_at_versioned_path(self, raw_client):
        """POST /api/v1/auth/login should exist (even if creds are wrong)."""
        response = await raw_client.post(
            "/api/v1/auth/login",
            json={"login": "nobody", "password": "wrong"},
        )
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_auth_register_at_versioned_path(self, raw_client):
        """POST /api/v1/auth/register should exist."""
        response = await raw_client.post(
            "/api/v1/auth/register",
            json={"username": "x", "email": "x@x.com", "password": "short"},
        )
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_foods_search_at_versioned_path(self, raw_client):
        """GET /api/v1/foods/search should exist (401 without auth is fine)."""
        response = await raw_client.get("/api/v1/foods/search?q=test")
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_logs_at_versioned_path(self, raw_client):
        """GET /api/v1/logs should exist."""
        response = await raw_client.get("/api/v1/logs")
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_profile_at_versioned_path(self, raw_client):
        """GET /api/v1/profile/foods should exist."""
        response = await raw_client.get("/api/v1/profile/foods")
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_recipes_at_versioned_path(self, raw_client):
        """GET /api/v1/recipes/ should exist."""
        response = await raw_client.get("/api/v1/recipes/")
        assert response.status_code != 404

    @pytest.mark.asyncio
    async def test_swagger_at_versioned_path(self, raw_client):
        """Swagger UI should be accessible at /api/v1/docs."""
        response = await raw_client.get("/api/v1/docs")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_not_under_versioned_prefix(self, raw_client):
        """Health check should NOT be at /api/v1/health — it's at /health."""
        response = await raw_client.get("/api/v1/health")
        assert response.status_code == 404
