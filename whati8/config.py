"""
Configuration settings for whati8 application.

Loads environment variables from .env file using Pydantic Settings.
All required variables are validated on startup.
"""

import tomllib
from pathlib import Path

from pydantic import Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from whati8.constants import JWT_MIN_SECRET_LENGTH, JWT_MIN_UNIQUE_CHARS


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
        min_length=JWT_MIN_SECRET_LENGTH,
        description=f"Secret key for JWT token signing (min {JWT_MIN_SECRET_LENGTH} chars)",
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

    # Embedding providers
    cohere_api_key: str = Field(
        default="",
        description="Cohere API key for embed-english-v3.0 embeddings and Rerank",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama base URL for local embedding fallback",
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

    # CORS Configuration
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="CORS allowed origins (comma-separated in env)",
    )

    # Environment
    environment: str = Field(
        default="dev",
        description="Environment: dev, staging, or prod",
    )
    docs_enabled: bool | None = Field(
        default=None,
        description="Enable Swagger docs (default: True for dev/staging, False for prod)",
    )

    # Rate Limiting
    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting",
    )
    rate_limit_per_minute: int = Field(
        default=10,
        ge=1,
        le=100,
        description="General API rate limit per minute",
    )
    rate_limit_ai_per_minute: int = Field(
        default=5,
        ge=1,
        le=20,
        description="AI endpoint rate limit per minute",
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

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret strength."""
        if len(v) < JWT_MIN_SECRET_LENGTH:
            raise ValueError(
                f"JWT secret must be at least {JWT_MIN_SECRET_LENGTH} characters"
            )
        unique_chars = len(set(v))
        if unique_chars < JWT_MIN_UNIQUE_CHARS:
            raise ValueError(
                f"JWT secret must have at least {JWT_MIN_UNIQUE_CHARS} unique characters"
            )
        if v == v[0] * len(v):
            raise ValueError("JWT secret cannot be all the same character")
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of dev, staging, prod."""
        valid = {"dev", "staging", "prod"}
        if v not in valid:
            raise ValueError(f"environment must be one of {valid}, got '{v}'")
        return v

    @model_validator(mode="after")
    def resolve_docs_enabled(self) -> "Settings":
        """If docs_enabled is None, default based on environment."""
        if self.docs_enabled is None:
            self.docs_enabled = self.environment != "prod"
        return self

    def get_cors_origins(self) -> list[str]:
        """Return CORS origins based on environment."""
        localhost_defaults = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
        if self.environment == "prod":
            return list(self.allowed_origins)
        # dev and staging: allowed_origins + localhost defaults (deduplicated)
        combined = list(self.allowed_origins)
        for origin in localhost_defaults:
            if origin not in combined:
                combined.append(origin)
        return combined

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_anthropic_key(cls, v: str) -> str:
        """Validate Anthropic API key format."""
        if v and not v.startswith("sk-ant-"):
            raise ValueError(
                "ANTHROPIC_API_KEY must start with 'sk-ant-' "
                "(get key from https://console.anthropic.com/)"
            )
        return v

    def get_async_database_url(self) -> str:
        """
        Get async-compatible database URL.

        Converts postgresql:// to postgresql+asyncpg:// for SQLAlchemy async engine.

        Returns:
            Async-compatible database URL string

        Raises:
            ValueError: If database URL format is invalid
        """
        url = str(self.database_url)

        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif not url.startswith("postgresql+asyncpg://"):
            raise ValueError(
                f"Invalid database URL format: {url}. "
                "Expected postgresql:// or postgresql+asyncpg://"
            )

        return url


# Global settings instance
settings = Settings()


# Load application config from config.toml
def load_config() -> dict:
    """Load configuration from config.toml."""
    config_path = Path(__file__).parent.parent / "config.toml"
    if not config_path.exists():
        # Return defaults if config.toml doesn't exist
        return {
            "search": {
                "keyword_weight": 0.5,
                "semantic_weight": 0.5,
                "rerank": {
                    "strategy": "word_count",
                    "word_threshold": 3,
                    "confidence_threshold": 0.6,
                    "top_k": 10,
                    "max_candidates": 50,
                },
            }
        }
    
    with open(config_path, "rb") as f:
        return tomllib.load(f)


app_config = load_config()
