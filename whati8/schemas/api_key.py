"""Schemas for API key management."""

from datetime import datetime

from pydantic import Field

from whati8.schemas.base import BaseORMModel, BaseRequestModel


class ApiKeyCreate(BaseRequestModel):
    """Request schema for creating an API key."""

    name: str = Field(..., min_length=1, max_length=100)


class ApiKeyResponse(BaseORMModel):
    """Response schema for an API key (no secrets)."""

    id: int
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None = None


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Response schema when a new API key is created — includes plaintext key (shown once)."""

    key: str
