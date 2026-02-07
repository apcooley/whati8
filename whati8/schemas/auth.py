"""Authentication schemas for request/response validation."""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserLogin(BaseModel):
    """Schema for user login (username or email + password)."""
    login: str  # Can be username or email
    password: str


class UserResponse(BaseModel):
    """Schema for user response (no password)."""
    id: int
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemy 2.0 compatibility


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    sub: int  # User ID (subject)
    exp: int  # Expiration timestamp
