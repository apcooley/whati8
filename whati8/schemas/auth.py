"""Authentication schemas for request/response validation."""

from datetime import datetime
from pydantic import EmailStr, Field

from whati8.constants import (
    PASSWORD_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
)
from whati8.schemas.base import BaseORMModel, BaseRequestModel


class UserCreate(BaseRequestModel):
    """Schema for user registration."""

    username: str = Field(
        ..., min_length=USERNAME_MIN_LENGTH, max_length=USERNAME_MAX_LENGTH
    )
    email: EmailStr
    password: str = Field(..., min_length=PASSWORD_MIN_LENGTH)


class UserLogin(BaseRequestModel):
    """Schema for user login (username or email + password)."""

    login: str  # Can be username or email
    password: str


class UserResponse(BaseORMModel):
    """Schema for user response (no password)."""

    id: int
    username: str
    email: str
    created_at: datetime


class Token(BaseORMModel):
    """Schema for JWT token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration
    refresh_token: str = ""


class RefreshRequest(BaseRequestModel):
    """Schema for refresh token request."""

    refresh_token: str


class LogoutRequest(BaseRequestModel):
    """Schema for logout request."""

    refresh_token: str


class TokenPayload(BaseORMModel):
    """Schema for JWT token payload."""

    sub: int  # User ID (subject)
    exp: int  # Expiration timestamp
