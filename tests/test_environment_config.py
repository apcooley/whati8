"""Tests for environment configuration and CORS tightening.

Step 2 of Phase 1 hardening: Environment awareness (dev/staging/prod) and CORS by environment.
"""

import pytest

from whati8.config import Settings


class TestEnvironmentConfig:
    """Environment field validation."""

    def test_default_environment_is_dev(self):
        """Default environment should be 'dev'."""
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
        )
        assert s.environment == "dev"

    def test_valid_environments(self):
        """dev, staging, and prod should all be accepted."""
        for env in ("dev", "staging", "prod"):
            s = Settings(
                database_url="postgresql://x:x@localhost/x",
                jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
                environment=env,
            )
            assert s.environment == env

    def test_invalid_environment_rejected(self):
        """Invalid environment values should be rejected at startup."""
        with pytest.raises(Exception):
            Settings(
                database_url="postgresql://x:x@localhost/x",
                jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
                environment="banana",
            )


class TestCORSByEnvironment:
    """CORS origins should be environment-aware."""

    def test_dev_allows_localhost(self):
        """Dev environment should include localhost origins."""
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
            environment="dev",
        )
        origins = s.get_cors_origins()
        assert any("localhost" in o for o in origins)

    def test_prod_no_localhost(self):
        """Prod environment should NOT include localhost origins."""
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
            environment="prod",
            allowed_origins=["https://whati8.example.com"],
        )
        origins = s.get_cors_origins()
        assert not any("localhost" in o for o in origins)

    def test_prod_uses_configured_origins(self):
        """Prod should use only the explicitly configured origins."""
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
            environment="prod",
            allowed_origins=["https://whati8.example.com"],
        )
        origins = s.get_cors_origins()
        assert "https://whati8.example.com" in origins

    def test_staging_allows_configured_plus_localhost(self):
        """Staging should allow both configured origins and localhost."""
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
            environment="staging",
            allowed_origins=["https://staging.whati8.example.com"],
        )
        origins = s.get_cors_origins()
        assert "https://staging.whati8.example.com" in origins
        assert any("localhost" in o for o in origins)

    def test_dev_default_origins(self):
        """Dev with no explicit origins should still have localhost defaults."""
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
            environment="dev",
        )
        origins = s.get_cors_origins()
        assert len(origins) > 0
        assert all("localhost" in o or "127.0.0.1" in o or "192.168" in o for o in origins)


class TestDocsToggle:
    """Swagger docs should be toggleable by environment."""

    def test_dev_docs_enabled(self):
        """Dev environment should have docs enabled."""
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
            environment="dev",
        )
        assert s.docs_enabled is True

    def test_prod_docs_disabled_by_default(self):
        """Prod environment should have docs disabled by default."""
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
            environment="prod",
            allowed_origins=["https://whati8.example.com"],
        )
        assert s.docs_enabled is False

    def test_prod_docs_can_be_force_enabled(self):
        """Prod docs can be explicitly enabled via config."""
        s = Settings(
            database_url="postgresql://x:x@localhost/x",
            jwt_secret="test-secret-key-with-enough-unique-chars-1234567890",
            environment="prod",
            allowed_origins=["https://whati8.example.com"],
            docs_enabled=True,
        )
        assert s.docs_enabled is True
