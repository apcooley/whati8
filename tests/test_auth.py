"""Tests for authentication system."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models import User
from whati8.schemas.auth import UserCreate
from whati8.services.auth import AuthService


@pytest.mark.auth
@pytest.mark.unit
class TestAuthService:
    """Test authentication service layer."""

    async def test_create_user(self, db_session: AsyncSession):
        """Test user creation with password hashing."""
        user_data = UserCreate(
            username="newuser",
            email="new@example.com",
            password="securepassword123",
        )

        user = await AuthService.create_user(db_session, user_data)

        assert user.id is not None
        assert user.username == "newuser"
        assert user.email == "new@example.com"
        assert user.password_hash != "securepassword123"
        assert user.password_hash.startswith("$2b$")  # bcrypt hash

    async def test_authenticate_user_success(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test successful user authentication."""
        authenticated_user = await AuthService.authenticate_user(
            db_session, test_user.username, "testpassword123"
        )

        assert authenticated_user is not None
        assert authenticated_user.id == test_user.id
        assert authenticated_user.username == test_user.username

    async def test_authenticate_user_wrong_password(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test authentication with wrong password."""
        result = await AuthService.authenticate_user(
            db_session, test_user.username, "wrongpassword"
        )

        assert result is None

    async def test_authenticate_user_nonexistent(self, db_session: AsyncSession):
        """Test authentication with nonexistent user."""
        result = await AuthService.authenticate_user(
            db_session, "nonexistent", "password"
        )

        assert result is None

    async def test_create_access_token(self, test_user: User):
        """Test JWT token creation."""
        token = AuthService.create_access_token(user_id=test_user.id)

        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long

    async def test_decode_token(self, test_user: User):
        """Test JWT token decoding."""
        token = AuthService.create_access_token(user_id=test_user.id)
        payload = AuthService.decode_token(token)

        assert payload.sub == test_user.id
        assert payload.exp > 0


@pytest.mark.auth
@pytest.mark.api
@pytest.mark.integration
class TestAuthAPI:
    """Test authentication API endpoints."""

    async def test_register_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test user registration via API."""
        response = await client.post(
            "/auth/register",
            json={
                "username": "apiuser",
                "email": "api@example.com",
                "password": "apipassword123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "apiuser"
        assert data["email"] == "api@example.com"
        assert "password" not in data
        assert "password_hash" not in data

    async def test_register_duplicate_username(
        self, client: AsyncClient, test_user: User
    ):
        """Test registration with duplicate username."""
        response = await client.post(
            "/auth/register",
            json={
                "username": test_user.username,  # Duplicate
                "email": "different@example.com",
                "password": "password123",
            },
        )

        assert response.status_code == 409
        assert "username" in response.json()["error"]["message"].lower()

    async def test_register_duplicate_email(self, client: AsyncClient, test_user: User):
        """Test registration with duplicate email."""
        response = await client.post(
            "/auth/register",
            json={
                "username": "differentuser",
                "email": test_user.email,  # Duplicate
                "password": "password123",
            },
        )

        assert response.status_code == 409
        assert "email" in response.json()["error"]["message"].lower()

    async def test_login_success(self, client: AsyncClient, test_user: User):
        """Test successful login."""
        response = await client.post(
            "/auth/login",
            json={
                "login": test_user.username,
                "password": "testpassword123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 50

    async def test_login_wrong_password(self, client: AsyncClient, test_user: User):
        """Test login with wrong password."""
        response = await client.post(
            "/auth/login",
            json={
                "login": test_user.username,
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401
        assert "incorrect" in response.json()["error"]["message"].lower()

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Test login with nonexistent user."""
        response = await client.post(
            "/auth/login",
            json={
                "login": "nonexistent",
                "password": "password",
            },
        )

        assert response.status_code == 401

    async def test_get_current_user(
        self, authenticated_client: AsyncClient, test_user: User
    ):
        """Test getting current user info."""
        response = await authenticated_client.get("/auth/me")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_user.id
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email
        assert "password" not in data

    async def test_get_current_user_no_token(self, client: AsyncClient):
        """Test getting current user without authentication."""
        response = await client.get("/auth/me")

        assert response.status_code == 401

    async def test_get_current_user_invalid_token(self, client: AsyncClient):
        """Test getting current user with invalid token."""
        client.headers["Authorization"] = "Bearer invalid_token"
        response = await client.get("/auth/me")

        assert response.status_code == 401
