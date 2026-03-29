"""Tests for refresh token system.

Step 5 of Phase 1 hardening: Short-lived access tokens + long-lived refresh tokens.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from whati8.api.app import create_app
from whati8.api.deps import get_db


@pytest.fixture
async def auth_client(db_session, seed_test_data, test_user):
    """Authenticated client that captures login response."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test/api/v1"
    ) as client:
        yield client


class TestLoginReturnsRefreshToken:
    """Login should return both access and refresh tokens."""

    @pytest.mark.asyncio
    async def test_login_returns_refresh_token(self, auth_client):
        """Login response should include a refresh_token field."""
        resp = await auth_client.post(
            "/auth/login",
            json={"login": "testuser", "password": "testpassword123"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert len(data["refresh_token"]) > 20

    @pytest.mark.asyncio
    async def test_login_access_token_still_works(self, auth_client):
        """Access token from login should authenticate requests."""
        resp = await auth_client.post(
            "/auth/login",
            json={"login": "testuser", "password": "testpassword123"},
        )
        token = resp.json()["access_token"]
        auth_client.headers["Authorization"] = f"Bearer {token}"

        resp = await auth_client.get("/auth/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == "testuser"


class TestRefreshEndpoint:
    """POST /auth/refresh should exchange refresh token for new access token."""

    @pytest.mark.asyncio
    async def test_refresh_returns_new_access_token(self, auth_client):
        """Valid refresh token should return a new access token."""
        # Login first
        resp = await auth_client.post(
            "/auth/login",
            json={"login": "testuser", "password": "testpassword123"},
        )
        refresh_token = resp.json()["refresh_token"]

        # Refresh
        resp = await auth_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert len(data["access_token"]) > 20

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token_returns_401(self, auth_client):
        """Invalid refresh token should return 401."""
        resp = await auth_client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid-token-garbage"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_refresh_returns_new_refresh_token(self, auth_client):
        """Refresh should also rotate the refresh token (return a new one)."""
        resp = await auth_client.post(
            "/auth/login",
            json={"login": "testuser", "password": "testpassword123"},
        )
        old_refresh = resp.json()["refresh_token"]

        resp = await auth_client.post(
            "/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert resp.status_code == 200
        new_refresh = resp.json().get("refresh_token")
        assert new_refresh is not None
        assert new_refresh != old_refresh


class TestLogoutEndpoint:
    """POST /auth/logout should revoke the refresh token."""

    @pytest.mark.asyncio
    async def test_logout_revokes_refresh_token(self, auth_client):
        """After logout, the refresh token should no longer work."""
        # Login
        resp = await auth_client.post(
            "/auth/login",
            json={"login": "testuser", "password": "testpassword123"},
        )
        data = resp.json()
        refresh_token = data["refresh_token"]
        access_token = data["access_token"]

        # Logout
        auth_client.headers["Authorization"] = f"Bearer {access_token}"
        resp = await auth_client.post(
            "/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200

        # Try to use revoked refresh token
        resp = await auth_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_requires_auth(self, auth_client):
        """Logout should require authentication."""
        resp = await auth_client.post(
            "/auth/logout",
            json={"refresh_token": "whatever"},
        )
        assert resp.status_code == 401


class TestRefreshTokenSecurity:
    """Security properties of refresh tokens."""

    @pytest.mark.asyncio
    async def test_used_refresh_token_cannot_be_reused(self, auth_client):
        """After refresh, the old refresh token should be invalidated (rotation)."""
        # Login
        resp = await auth_client.post(
            "/auth/login",
            json={"login": "testuser", "password": "testpassword123"},
        )
        refresh_token = resp.json()["refresh_token"]

        # Use it once
        resp = await auth_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200

        # Try to reuse the old one
        resp = await auth_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 401


class TestRefreshTokenExpiry:
    """Expired refresh tokens should be rejected."""

    @pytest.mark.asyncio
    async def test_expired_refresh_token_rejected(self, auth_client, db_session):
        """A refresh token past its expiry should return 401."""
        from datetime import datetime, timedelta, timezone
        from whati8.services.auth import AuthService
        from whati8.models.refresh_token import RefreshToken
        from sqlalchemy import select
        import hashlib

        # Login to get a refresh token
        resp = await auth_client.post(
            "/auth/login",
            json={"login": "testuser", "password": "testpassword123"},
        )
        refresh_token = resp.json()["refresh_token"]

        # Manually expire it in the DB
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        result = await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one()
        rt.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await db_session.commit()

        # Try to refresh with expired token
        resp = await auth_client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 401
