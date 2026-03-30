"""Tests for staging environment configuration.

Validates:
- fly.staging.toml exists with correct staging config
- Staging app name is different from prod
- Staging has ENVIRONMENT=staging
- Staging enables docs and registration (for testing)
- Deploy scripts exist and are executable
- Deployment docs exist
- fly.staging.toml doesn't contain prod secrets
"""

import pytest
import tomllib
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


class TestFlyStagingToml:
    """Validate fly.staging.toml configuration."""

    @pytest.fixture(autouse=True)
    def load_staging_toml(self):
        path = PROJECT_ROOT / "fly.staging.toml"
        assert path.exists(), "fly.staging.toml not found at project root"
        with open(path, "rb") as f:
            self.config = tomllib.load(f)

    def test_app_name_is_staging(self):
        """Staging app name must be different from prod."""
        assert "staging" in self.config["app"], (
            f"Staging app name should contain 'staging': {self.config['app']}"
        )

    def test_app_name_not_prod(self):
        """Staging must not point to the prod app."""
        prod_toml = PROJECT_ROOT / "fly.toml"
        with open(prod_toml, "rb") as f:
            prod_config = tomllib.load(f)
        assert self.config["app"] != prod_config["app"], (
            "fly.staging.toml must not use the same app name as fly.toml"
        )

    def test_environment_is_staging(self):
        """ENVIRONMENT must be staging."""
        env = self.config.get("env", {})
        assert env.get("ENVIRONMENT") == "staging"

    def test_docs_enabled_in_staging(self):
        """Staging should have docs enabled for testing."""
        env = self.config.get("env", {})
        # Either DOCS_ENABLED=true or not set (defaults to true for non-prod)
        docs = env.get("DOCS_ENABLED", "true").lower()
        assert docs != "false", "Docs should be enabled in staging"

    def test_registration_enabled_in_staging(self):
        """Staging should allow registration for testing."""
        env = self.config.get("env", {})
        reg = env.get("REGISTRATION_ENABLED", "true").lower()
        assert reg == "true", "Registration should be enabled in staging"

    def test_has_build_section(self):
        """Must have a build section pointing to Dockerfile."""
        assert "build" in self.config
        assert self.config["build"].get("dockerfile") == "Dockerfile"

    def test_has_http_service(self):
        """Must have HTTP service on port 9428."""
        assert "http_service" in self.config
        assert self.config["http_service"]["internal_port"] == 9428

    def test_has_health_check(self):
        """Must have a health check."""
        svc = self.config.get("http_service", {})
        checks = svc.get("checks", [])
        has_check = False
        if isinstance(checks, list):
            for check in checks:
                if check.get("path") == "/health":
                    has_check = True
        assert has_check, "No health check configured"

    def test_no_secrets_in_staging_toml(self):
        """fly.staging.toml must NOT contain secret values in [env]."""
        env = self.config.get("env", {})
        secret_keys = ["JWT_SECRET", "ANTHROPIC_API_KEY", "COHERE_API_KEY", "DATABASE_URL"]
        for key in secret_keys:
            assert key not in env, f"{key} should be a fly secret, not in [env]"

    def test_allowed_origins_for_staging(self):
        """Staging CORS should include the staging URL."""
        env = self.config.get("env", {})
        origins = env.get("ALLOWED_ORIGINS", "")
        assert "fly.dev" in origins or "staging" in origins or "localhost" in origins, (
            "Staging ALLOWED_ORIGINS should include staging or localhost URLs"
        )


class TestDeployScripts:
    """Validate deployment helper scripts."""

    def test_staging_deploy_script_exists(self):
        """scripts/deploy-staging.sh must exist."""
        script = PROJECT_ROOT / "scripts" / "deploy-staging.sh"
        assert script.exists(), "scripts/deploy-staging.sh not found"

    def test_prod_deploy_script_exists(self):
        """scripts/deploy-prod.sh must exist."""
        script = PROJECT_ROOT / "scripts" / "deploy-prod.sh"
        assert script.exists(), "scripts/deploy-prod.sh not found"

    def test_staging_script_is_executable(self):
        """Staging deploy script must be executable."""
        script = PROJECT_ROOT / "scripts" / "deploy-staging.sh"
        assert os.access(script, os.X_OK), "deploy-staging.sh is not executable"

    def test_prod_script_is_executable(self):
        """Prod deploy script must be executable."""
        script = PROJECT_ROOT / "scripts" / "deploy-prod.sh"
        assert os.access(script, os.X_OK), "deploy-prod.sh is not executable"

    def test_prod_script_has_confirmation(self):
        """Prod deploy script must include a confirmation prompt."""
        script = PROJECT_ROOT / "scripts" / "deploy-prod.sh"
        content = script.read_text()
        assert "confirm" in content.lower() or "y/n" in content.lower() or "read" in content.lower(), (
            "Prod deploy script must include a confirmation prompt"
        )

    def test_staging_script_uses_staging_toml(self):
        """Staging script must use fly.staging.toml."""
        script = PROJECT_ROOT / "scripts" / "deploy-staging.sh"
        content = script.read_text()
        assert "fly.staging.toml" in content, (
            "Staging script must reference fly.staging.toml"
        )

    def test_prod_script_uses_prod_toml(self):
        """Prod script must use fly.toml (not staging)."""
        script = PROJECT_ROOT / "scripts" / "deploy-prod.sh"
        content = script.read_text()
        assert "fly.toml" in content and "staging" not in content.split("fly.toml")[0][-20:], (
            "Prod script must reference fly.toml"
        )


class TestDeploymentDocs:
    """Verify deployment documentation exists."""

    def test_deployment_docs_exist(self):
        """docs/DEPLOYMENT.md must exist."""
        docs = PROJECT_ROOT / "docs" / "DEPLOYMENT.md"
        assert docs.exists(), "docs/DEPLOYMENT.md not found"

    def test_deployment_docs_cover_staging(self):
        """Deployment docs must describe staging workflow."""
        docs = PROJECT_ROOT / "docs" / "DEPLOYMENT.md"
        content = docs.read_text().lower()
        assert "staging" in content, "Deployment docs must cover staging"

    def test_deployment_docs_cover_rollback(self):
        """Deployment docs must describe rollback procedure."""
        docs = PROJECT_ROOT / "docs" / "DEPLOYMENT.md"
        content = docs.read_text().lower()
        assert "rollback" in content, "Deployment docs must cover rollback"
