"""Tests for request body size limits.

Step 3 of Phase 1 hardening: Enforce max request body size to prevent abuse.
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


class TestBodySizeLimits:
    """Request body size enforcement."""

    @pytest.mark.asyncio
    async def test_normal_request_passes(self, raw_client):
        """A small JSON body should pass through fine."""
        response = await raw_client.post(
            "/auth/login",
            json={"login": "test", "password": "test"},
        )
        # 401 means it got through to the handler (body accepted)
        assert response.status_code != 413

    @pytest.mark.asyncio
    async def test_oversized_body_rejected(self, raw_client):
        """A body exceeding the default limit (1MB) should return 413."""
        # 2MB of JSON data
        big_payload = {"data": "x" * (2 * 1024 * 1024)}
        response = await raw_client.post(
            "/auth/login",
            json=big_payload,
        )
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_just_under_limit_passes(self, raw_client):
        """A body just under 1MB should pass."""
        # ~500KB — well under limit
        payload = {"data": "x" * (500 * 1024)}
        response = await raw_client.post(
            "/auth/login",
            json=payload,
        )
        assert response.status_code != 413

    @pytest.mark.asyncio
    async def test_413_returns_json_error(self, raw_client):
        """413 response should be a JSON error, not plain text."""
        big_payload = {"data": "x" * (2 * 1024 * 1024)}
        response = await raw_client.post(
            "/auth/login",
            json=big_payload,
        )
        assert response.status_code == 413
        data = response.json()
        assert "error" in data or "detail" in data

    @pytest.mark.asyncio
    async def test_get_requests_unaffected(self, raw_client):
        """GET requests (no body) should not be affected by body limits."""
        response = await raw_client.get("/foods/search?q=test")
        assert response.status_code != 413
