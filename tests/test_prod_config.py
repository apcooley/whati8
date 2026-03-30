"""Tests for production configuration safety.

Validates:
- Fly.io postgres:// URL format handled correctly
- Swagger docs disabled in prod
- CORS origins locked down in prod (no localhost)
- fly.toml env has ALLOWED_ORIGINS for the production domain
- Debug mode off in prod
- JWT secret validation still works
"""

import pytest
from unittest.mock import patch
import os


class TestDatabaseUrlConversion:
    """Fly.io uses postgres:// but SQLAlchemy needs postgresql://."""

    def test_postgres_scheme_converted(self):
        """postgres://... should become postgresql+asyncpg://..."""
        from whati8.config import Settings

        with patch.dict(os.environ, {
            "DATABASE_URL": "postgres://user:pass@host:5432/db",
            "JWT_SECRET": "test-secret-that-is-long-enough-32chars",
        }, clear=False):
            s = Settings(
                database_url="postgres://user:pass@host:5432/db",
                jwt_secret="test-secret-that-is-long-enough-32chars",
            )
            url = s.get_async_database_url()
            assert url.startswith("postgresql+asyncpg://")
            assert "user:pass@host:5432/db" in url

    def test_postgresql_scheme_works(self):
        """Standard postgresql://... should also work."""
        from whati8.config import Settings

        s = Settings(
            database_url="postgresql://user:pass@host:5432/db",
            jwt_secret="test-secret-that-is-long-enough-32chars",
        )
        url = s.get_async_database_url()
        assert url.startswith("postgresql+asyncpg://")

    def test_asyncpg_scheme_passthrough(self):
        """postgresql+asyncpg://... should pass through unchanged."""
        from whati8.config import Settings

        s = Settings(
            database_url="postgresql+asyncpg://user:pass@host:5432/db",
            jwt_secret="test-secret-that-is-long-enough-32chars",
        )
        url = s.get_async_database_url()
        assert url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_fly_connection_string_format(self):
        """Real Fly.io connection string format should work."""
        from whati8.config import Settings

        fly_url = "postgres://whati8_app:somepass@whati8-db.flycast:5432/whati8_app?sslmode=disable"
        s = Settings(
            database_url=fly_url,
            jwt_secret="test-secret-that-is-long-enough-32chars",
        )
        url = s.get_async_database_url()
        assert url.startswith("postgresql+asyncpg://")
        assert "whati8_app" in url
        assert "whati8-db.flycast" in url


class TestProdDocsDisabled:
    """Swagger docs must be disabled in production."""

    def test_docs_disabled_in_prod(self):
        from whati8.config import Settings

        s = Settings(
            environment="prod",
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-that-is-long-enough-32chars",
        )
        assert s.docs_enabled is False

    def test_docs_enabled_in_dev(self):
        from whati8.config import Settings

        s = Settings(
            environment="dev",
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-that-is-long-enough-32chars",
        )
        assert s.docs_enabled is True


class TestProdCorsOrigins:
    """CORS origins must be locked down in production."""

    def test_prod_no_localhost_origins(self):
        """Prod should NOT include localhost origins."""
        from whati8.config import Settings

        s = Settings(
            environment="prod",
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-that-is-long-enough-32chars",
            allowed_origins=["https://whati8.app"],
        )
        origins = s.get_cors_origins()
        for origin in origins:
            assert "localhost" not in origin, f"localhost origin leaked into prod: {origin}"
            assert "127.0.0.1" not in origin, f"127.0.0.1 origin leaked into prod: {origin}"

    def test_prod_returns_only_allowed_origins(self):
        """Prod should return exactly the configured allowed_origins."""
        from whati8.config import Settings

        s = Settings(
            environment="prod",
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-that-is-long-enough-32chars",
            allowed_origins=["https://whati8.app"],
        )
        origins = s.get_cors_origins()
        assert origins == ["https://whati8.app"]

    def test_dev_includes_localhost(self):
        """Dev should include localhost defaults."""
        from whati8.config import Settings

        s = Settings(
            environment="dev",
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-that-is-long-enough-32chars",
        )
        origins = s.get_cors_origins()
        assert any("localhost" in o for o in origins)


class TestFlyTomlProdEnv:
    """fly.toml must have production-safe environment config."""

    def test_allowed_origins_set(self):
        """fly.toml env must include ALLOWED_ORIGINS with the production domain."""
        import tomllib
        from pathlib import Path

        fly_toml = Path(__file__).parent.parent / "fly.toml"
        with open(fly_toml, "rb") as f:
            config = tomllib.load(f)

        env = config.get("env", {})
        origins = env.get("ALLOWED_ORIGINS", "")
        assert "whati8.app" in origins, (
            "fly.toml [env] must include ALLOWED_ORIGINS with https://whati8.app"
        )

    def test_environment_is_prod(self):
        """fly.toml env must set ENVIRONMENT=prod."""
        import tomllib
        from pathlib import Path

        fly_toml = Path(__file__).parent.parent / "fly.toml"
        with open(fly_toml, "rb") as f:
            config = tomllib.load(f)

        assert config["env"]["ENVIRONMENT"] == "prod"

    def test_debug_not_enabled(self):
        """fly.toml must NOT set DEBUG=true."""
        import tomllib
        from pathlib import Path

        fly_toml = Path(__file__).parent.parent / "fly.toml"
        with open(fly_toml, "rb") as f:
            config = tomllib.load(f)

        env = config.get("env", {})
        debug = env.get("DEBUG", "false").lower()
        assert debug != "true", "DEBUG must not be true in production fly.toml"
