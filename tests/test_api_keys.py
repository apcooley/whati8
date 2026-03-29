"""Tests for API key authentication system.

Step 6 of Phase 1 hardening: API key auth for scripts, MCP, and non-browser clients.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from whati8.api.app import create_app
from whati8.api.deps import get_db


@pytest.fixture
async def auth_client(db_session, seed_test_data, test_user):
    """Authenticated client with JWT token."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test/api/v1"
    ) as client:
        resp = await client.post(
            "/auth/login",
            json={"login": "testuser", "password": "testpassword123"},
        )
        client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield client


class TestCreateApiKey:
    """POST /auth/api-keys — create a new API key."""

    @pytest.mark.asyncio
    async def test_create_returns_key_with_prefix(self, auth_client):
        """Created API key should start with 'wi8_' prefix."""
        resp = await auth_client.post(
            "/auth/api-keys",
            json={"name": "My Script"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "key" in data
        assert data["key"].startswith("wi8_")
        assert len(data["key"]) > 20

    @pytest.mark.asyncio
    async def test_create_returns_key_metadata(self, auth_client):
        """Response should include id, name, key_prefix, created_at."""
        resp = await auth_client.post(
            "/auth/api-keys",
            json={"name": "Test Key"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["name"] == "Test Key"
        assert "key_prefix" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_requires_auth(self, auth_client):
        """Creating an API key requires authentication."""
        auth_client.headers.pop("Authorization", None)
        resp = await auth_client.post(
            "/auth/api-keys",
            json={"name": "Sneaky Key"},
        )
        assert resp.status_code in (401, 403)


class TestListApiKeys:
    """GET /auth/api-keys — list user's API keys."""

    @pytest.mark.asyncio
    async def test_list_returns_keys_without_secrets(self, auth_client):
        """List should show key metadata but NOT the full key."""
        # Create a key first
        await auth_client.post(
            "/auth/api-keys",
            json={"name": "List Test Key"},
        )

        resp = await auth_client.get("/auth/api-keys")
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) >= 1
        for key in keys:
            assert "id" in key
            assert "name" in key
            assert "key_prefix" in key
            # Full key should NOT be in the list
            assert "key" not in key

    @pytest.mark.asyncio
    async def test_list_only_own_keys(self, auth_client):
        """Users should only see their own keys."""
        await auth_client.post(
            "/auth/api-keys",
            json={"name": "My Key"},
        )
        resp = await auth_client.get("/auth/api-keys")
        keys = resp.json()
        assert all(k["name"] != "Someone Elses Key" for k in keys)


class TestRevokeApiKey:
    """DELETE /auth/api-keys/{id} — revoke an API key."""

    @pytest.mark.asyncio
    async def test_revoke_key(self, auth_client):
        """Deleting a key should return 204."""
        resp = await auth_client.post(
            "/auth/api-keys",
            json={"name": "To Delete"},
        )
        key_id = resp.json()["id"]

        resp = await auth_client.delete(f"/auth/api-keys/{key_id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_revoked_key_no_longer_listed(self, auth_client):
        """After revocation, key should not appear in list."""
        resp = await auth_client.post(
            "/auth/api-keys",
            json={"name": "Will Be Gone"},
        )
        key_id = resp.json()["id"]

        await auth_client.delete(f"/auth/api-keys/{key_id}")

        resp = await auth_client.get("/auth/api-keys")
        keys = resp.json()
        assert all(k["id"] != key_id for k in keys)


class TestApiKeyAuth:
    """API key should authenticate requests like JWT does."""

    @pytest.mark.asyncio
    async def test_api_key_authenticates_bearer(self, auth_client):
        """Authorization: Bearer wi8_... should work."""
        # Create a key
        resp = await auth_client.post(
            "/auth/api-keys",
            json={"name": "Auth Test"},
        )
        api_key = resp.json()["key"]

        # Use it to call /auth/me
        auth_client.headers["Authorization"] = f"Bearer {api_key}"
        resp = await auth_client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_api_key_authenticates_x_api_key(self, auth_client):
        """X-API-Key header should also work."""
        resp = await auth_client.post(
            "/auth/api-keys",
            json={"name": "Header Test"},
        )
        api_key = resp.json()["key"]

        # Remove JWT, use X-API-Key instead
        auth_client.headers.pop("Authorization", None)
        auth_client.headers["X-API-Key"] = api_key
        resp = await auth_client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"

    @pytest.mark.asyncio
    async def test_invalid_api_key_returns_401(self, auth_client):
        """Invalid API key should return 401."""
        auth_client.headers["Authorization"] = "Bearer wi8_invalid_garbage_key"
        resp = await auth_client.get("/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_revoked_key_returns_401(self, auth_client):
        """A revoked API key should no longer authenticate."""
        # Create and then revoke
        resp = await auth_client.post(
            "/auth/api-keys",
            json={"name": "Revoke Auth Test"},
        )
        api_key = resp.json()["key"]
        key_id = resp.json()["id"]

        await auth_client.delete(f"/auth/api-keys/{key_id}")

        # Try to use the revoked key
        auth_client.headers["Authorization"] = f"Bearer {api_key}"
        resp = await auth_client.get("/auth/me")
        assert resp.status_code == 401
