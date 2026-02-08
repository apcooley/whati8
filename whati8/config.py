"""
Configuration settings for whati8 application.

Loads environment variables from .env file using Pydantic Settings.
All required variables are validated on startup.
"""

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: PostgresDsn = Field(
        ...,
        description="PostgreSQL database URL (postgresql+asyncpg://user:pass@host:port/db)",
    )

    # USDA Food Data Central API
    usda_api_key: str = Field(
        ...,
        min_length=1,
        description="USDA FDC API key from https://fdc.nal.usda.gov/api-key-signup.html",
    )

    # Authentication
    jwt_secret: str = Field(
        ...,
        min_length=32,
        description="Secret key for JWT token signing (min 32 chars)",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm",
    )
    jwt_expiration_hours: int = Field(
        default=24,
        ge=1,
        description="JWT token expiration time in hours",
    )

    # AI/LLM Service
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude integration",
    )
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Anthropic model ID for food parsing",
    )
    openai_api_key: str = Field(
        default="",
        description="OpenAI API key (alternative to Anthropic)",
    )

    # Application
    debug: bool = Field(
        default=False,
        description="Enable debug mode",
    )
    log_level: str = Field(
        default="info",
        description="Logging level (debug, info, warning, error, critical)",
    )

    # Database connection pool settings
    db_pool_size: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Database connection pool size",
    )
    db_max_overflow: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum overflow connections",
    )
    db_pool_recycle: int = Field(
        default=3600,
        ge=60,
        description="Connection recycle time in seconds",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Global settings instance
settings = Settings()
