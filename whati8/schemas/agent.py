"""Pydantic schemas for conversational agent API."""

from datetime import datetime

from pydantic import Field

from whati8.schemas.base import BaseORMModel, BaseRequestModel


class AgentChatRequest(BaseRequestModel):
    """Request schema for agent chat endpoint."""

    message: str = Field(..., min_length=1, max_length=1000, description="User message")
    session_id: str = Field(
        ..., description="Session ID for conversation continuity"
    )
    user_timezone: str = Field(
        "UTC",
        description="User's IANA timezone (e.g., 'America/Los_Angeles')",
        examples=["America/New_York", "Europe/London", "Asia/Tokyo"],
    )
    conversation_history: list[dict] | None = Field(
        None, max_length=20, description="Optional conversation history from client"
    )


class AgentMessage(BaseORMModel):
    """Schema for a single message in conversation."""

    role: str = Field(..., pattern="^(user|assistant)$", description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    tool_calls: list[dict] | None = Field(None, description="Tool calls made")
    metadata: dict | None = Field(None, description="Additional metadata")


class AgentChatResponse(BaseORMModel):
    """Response schema for agent chat endpoint."""

    message: str = Field(..., description="Assistant's response message")
    session_id: str = Field(..., description="Session ID for conversation")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )
    requires_form: bool = Field(
        False, description="Whether user confirmation is required"
    )
    form_data: dict | None = Field(None, description="Form data if confirmation needed")
    tool_results: list[dict] | None = Field(
        None, description="Results from tool executions"
    )
