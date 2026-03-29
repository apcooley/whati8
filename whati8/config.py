"""
Configuration settings for whati8 application.

Loads environment variables from .env file using Pydantic Settings.
All required variables are validated on startup.
"""

import tomllib
from pathlib import Path
from typing import Any, Self, Tuple, Type

from pydantic import BaseModel, Field, PostgresDsn, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from whati8.constants import JWT_MIN_SECRET_LENGTH, JWT_MIN_UNIQUE_CHARS


class RerankSettings(BaseModel):
    """Rerank configuration settings."""

    strategy: str = Field(
        default="word_count",
        description="Rerank strategy: 'word_count', 'confidence', 'always', or 'never'",
    )
    word_threshold: int = Field(
        default=3,
        description="Minimum word count to trigger reranking (word_count strategy)",
    )
    confidence_threshold: float = Field(
        default=0.6,
        description="Confidence threshold to trigger reranking (confidence strategy)",
    )
    top_k: int = Field(
        default=10,
        description="Number of top results to return after reranking",
    )
    max_candidates: int = Field(
        default=50,
        description="Maximum candidates to send to Rerank API",
    )


class SearchSettings(BaseModel):
    """Search configuration settings."""

    keyword_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for keyword search in hybrid search (0.0–1.0)",
    )
    semantic_weight: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Weight for semantic search in hybrid search (0.0–1.0)",
    )
    rerank: RerankSettings = Field(
        default_factory=RerankSettings,
        description="Rerank configuration",
    )


class TomlConfigSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that loads from config.toml.

    Reads config.toml once on init, caches the result, and maps
    the [search] / [search.rerank] sections to SearchSettings.
    """

    def __init__(self, settings_cls: Type["Settings"]) -> None:
        super().__init__(settings_cls)
        self._toml_data = self._load_toml()

    def get_field_value(self, field: Any, field_name: str) -> Tuple[Any, str, bool]:
        """Get field value from config.toml."""
        if field_name == "search":
            parsed = self._parse_search(self._toml_data)
            if parsed is not None:
                return parsed, field_name, False
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        """Return all settings from config.toml."""
        result: dict[str, Any] = {}
        parsed = self._parse_search(self._toml_data)
        if parsed is not None:
            result["search"] = parsed
        return result

    @staticmethod
    def _parse_search(config: dict) -> SearchSettings | None:
        """Parse [search] section from TOML into SearchSettings."""
        if "search" not in config:
            return None
        toml_search = config["search"]
        rerank_data = toml_search.get("rerank", {})
        return SearchSettings(
            keyword_weight=toml_search.get("keyword_weight", 0.5),
            semantic_weight=toml_search.get("semantic_weight", 0.5),
            rerank=RerankSettings(**rerank_data) if rerank_data else RerankSettings(),
        )

    @staticmethod
    def _load_toml() -> dict:
        """Load config.toml file. Returns empty dict if missing or malformed."""
        config_path = Path(__file__).parent.parent / "config.toml"
        if not config_path.exists():
            return {}
        try:
            with open(config_path, "rb") as f:
                return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            import logging

            logging.getLogger(__name__).warning(
                f"Invalid config.toml, using defaults: {e}"
            )
            return {}


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
        default=1,
        ge=1,
        description="JWT token expiration time in hours",
    )
    refresh_token_expiration_days: int = Field(
        default=30,
        ge=1,
        description="Refresh token expiration time in days",
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

    # Request body size limit
    max_body_size: int = Field(
        default=1_048_576,
        description="Max request body size in bytes",
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

    # Search settings (nested model)
    search: SearchSettings = Field(
        default_factory=SearchSettings,
        description="Search configuration",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources priority.

        Priority (highest to lowest):
        1. init_settings - values passed to constructor
        2. env_settings - environment variables
        3. dotenv_settings - .env file
        4. toml_settings - config.toml file (custom)
        5. file_secret_settings - secrets files
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
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
    def resolve_docs_enabled(self) -> Self:
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
