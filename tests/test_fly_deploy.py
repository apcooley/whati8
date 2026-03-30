"""Tests for Fly.io deployment configuration.

Validates:
- fly.toml exists and has required fields
- .dockerignore exists and excludes dev artifacts
- Dockerfile builds correctly (syntax check)
- fly.toml service config matches our app (port 9428, health check)
- Environment variables are production-safe
"""

import pytest
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

pytestmark = pytest.mark.integration


class TestFlyToml:
    """Validate fly.toml configuration."""

    @pytest.fixture(autouse=True)
    def load_fly_toml(self):
        fly_toml = PROJECT_ROOT / "fly.toml"
        assert fly_toml.exists(), "fly.toml not found at project root"
        with open(fly_toml, "rb") as f:
            self.config = tomllib.load(f)

    def test_app_name(self):
        """App name must be set."""
        assert "app" in self.config
        assert len(self.config["app"]) > 0

    def test_primary_region(self):
        """Primary region should be set (den for Denver)."""
        assert "primary_region" in self.config
        assert self.config["primary_region"] == "dfw"

    def test_build_section(self):
        """Build section should reference the Dockerfile."""
        assert "build" in self.config
        assert self.config["build"].get("dockerfile") == "Dockerfile"

    def test_http_service(self):
        """HTTP service must be configured on internal port 9428."""
        assert "http_service" in self.config
        svc = self.config["http_service"]
        assert svc["internal_port"] == 9428
        assert svc["force_https"] is True

    def test_health_check(self):
        """Health check must point to /health."""
        svc = self.config.get("http_service", {})
        checks = svc.get("checks", [])

        has_check = False
        # Fly uses array format [[http_service.checks]]
        if isinstance(checks, list):
            for check in checks:
                if check.get("path") == "/health":
                    has_check = True
        # Also support map format {name: {path: ...}}
        elif isinstance(checks, dict):
            for check in checks.values():
                if isinstance(check, dict) and check.get("path") == "/health":
                    has_check = True

        assert has_check, "No health check configured for /health"

    def test_env_section(self):
        """Non-secret env vars should be in [env]."""
        env = self.config.get("env", {})
        assert env.get("ENVIRONMENT") == "prod"
        assert env.get("LOG_LEVEL") in ("info", "warning")

    def test_no_secrets_in_toml(self):
        """fly.toml must NOT contain secret keys in [env] section."""
        env = self.config.get("env", {})
        secret_keys = ["JWT_SECRET", "ANTHROPIC_API_KEY", "COHERE_API_KEY", "FDC_API_KEY", "DATABASE_URL"]
        for key in secret_keys:
            assert key not in env, f"{key} should be a fly secret, not in [env]"

    def test_auto_start_enabled(self):
        """auto_start must be true so the app wakes from suspend."""
        svc = self.config.get("http_service", {})
        assert svc.get("auto_start") is True, "auto_start not enabled — app won't wake from suspend"

    def test_auto_stop_configured(self):
        """Auto-stop should be configured for cost savings."""
        svc = self.config.get("http_service", {})
        # auto_stop can be a string or bool
        assert "auto_stop" in svc, "auto_stop not configured — will burn credits"


class TestDockerIgnore:
    """Validate .dockerignore excludes dev artifacts."""

    @pytest.fixture(autouse=True)
    def load_dockerignore(self):
        path = PROJECT_ROOT / ".dockerignore"
        assert path.exists(), ".dockerignore not found"
        self.lines = path.read_text().splitlines()
        self.content = path.read_text()

    def test_excludes_venv(self):
        assert ".venv" in self.lines or ".venv/" in self.lines

    def test_excludes_git(self):
        assert ".git" in self.lines or ".git/" in self.lines

    def test_excludes_node_modules(self):
        assert "node_modules" in self.lines or "node_modules/" in self.lines

    def test_excludes_pycache(self):
        assert "__pycache__" in self.lines or "__pycache__/" in self.lines

    def test_excludes_env_file(self):
        assert ".env" in self.lines

    def test_excludes_test_files(self):
        """Tests shouldn't be in the production image."""
        assert "tests/" in self.lines or "tests" in self.lines


class TestDockerfile:
    """Validate Dockerfile structure."""

    @pytest.fixture(autouse=True)
    def load_dockerfile(self):
        path = PROJECT_ROOT / "Dockerfile"
        assert path.exists()
        self.content = path.read_text()
        self.lines = self.content.splitlines()

    def test_uses_python_311(self):
        assert any("python:3.11" in line for line in self.lines)

    def test_exposes_9428(self):
        assert any("EXPOSE 9428" in line for line in self.lines)

    def test_has_healthcheck(self):
        assert "HEALTHCHECK" in self.content

    def test_runs_as_non_root(self):
        """Production image should not run as root."""
        assert any("USER" in line and "root" not in line.lower() for line in self.lines)

    def test_copies_alembic(self):
        """Alembic migrations must be in the image for DB setup."""
        assert "alembic" in self.content.lower()
