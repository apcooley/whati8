"""Tests for per-IP auth rate limiting.

Step 4 of Phase 1 hardening: Strict rate limits on authentication endpoints.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from whati8.api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def raw_client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test/api/v1"
    ) as client:
        yield client


class TestLoginRateLimit:
    """POST /auth/login should be rate limited per IP."""

    @pytest.mark.asyncio
    async def test_first_login_attempt_not_rate_limited(self, raw_client):
        """First attempt should not be rate limited (even if creds are wrong)."""
        response = await raw_client.post(
            "/auth/login",
            json={"login": "nobody", "password": "wrong"},
        )
        # 401 = auth failed, which means it got through rate limiting
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_rate_limited_after_burst(self, raw_client):
        """After exceeding login rate limit, should get 429."""
        # Fire more than the per-minute limit (5/min)
        for i in range(7):
            response = await raw_client.post(
                "/auth/login",
                json={"login": f"user{i}", "password": "wrong"},
            )

        # At least the last request should be 429
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_returns_retry_after(self, raw_client):
        """429 response should include Retry-After header."""
        for i in range(7):
            response = await raw_client.post(
                "/auth/login",
                json={"login": f"user{i}", "password": "wrong"},
            )

        assert response.status_code == 429
        assert "retry-after" in response.headers or "Retry-After" in response.headers


class TestRegisterRateLimit:
    """POST /auth/register should be rate limited per IP."""

    @pytest.mark.asyncio
    async def test_register_rate_limited_after_burst(self, raw_client):
        """After exceeding register rate limit (3/min), should get 429."""
        for i in range(5):
            response = await raw_client.post(
                "/auth/register",
                json={
                    "username": f"user{i}",
                    "email": f"user{i}@test.com",
                    "password": "testpassword123",
                },
            )

        # At least the last request should be 429
        assert response.status_code == 429


class TestAuthRateLimitIsolation:
    """Auth rate limits should not affect other endpoints."""

    @pytest.mark.asyncio
    async def test_food_search_not_affected_by_auth_limits(self, raw_client):
        """Food search should still work even if auth is rate limited."""
        # Burn through auth rate limit
        for i in range(7):
            await raw_client.post(
                "/auth/login",
                json={"login": f"user{i}", "password": "wrong"},
            )

        # Food search should still work (different endpoint, different limit)
        response = await raw_client.get("/foods/search?q=test")
        assert response.status_code != 429
