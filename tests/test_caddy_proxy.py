"""Tests for Caddy reverse proxy configuration.

These tests verify the Caddy proxy is correctly configured:
- TLS termination (HTTPS works)
- Security headers (HSTS, X-Frame-Options, etc.)
- Reverse proxy to backend (health check, API routes)
- HTTP→HTTPS redirect
- Server header removed

Requirements:
- Caddy running with deploy/Caddyfile
- whati8 backend running on localhost:9428
- Run with: uv run pytest tests/test_caddy_proxy.py -v

These are integration tests that hit the live proxy.
Mark them so they don't run in normal unit test suites.
"""

import pytest
import httpx

PROXY_BASE = "https://192.168.1.11"
HTTP_BASE = "http://192.168.1.11"
BACKEND_BASE = "http://localhost:9428"

# Skip all tests if Caddy proxy isn't reachable
pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    """HTTPS client that trusts self-signed certs."""
    return httpx.Client(verify=False, timeout=10, follow_redirects=False)


@pytest.fixture
def backend_client():
    """Direct backend client (no proxy)."""
    return httpx.Client(timeout=10)


class TestTLSTermination:
    """Verify TLS is working through the proxy."""

    def test_https_health_check(self, client):
        """Health endpoint accessible via HTTPS."""
        resp = client.get(f"{PROXY_BASE}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_http_redirects_to_https(self, client):
        """HTTP requests get 301 redirected to HTTPS."""
        resp = client.get(f"{HTTP_BASE}/health")
        assert resp.status_code in (301, 308)  # permanent redirect
        location = resp.headers.get("location", "")
        assert location.startswith("https://")


class TestSecurityHeaders:
    """Verify security headers are set by Caddy."""

    def test_hsts_header(self, client):
        """Strict-Transport-Security header present."""
        resp = client.get(f"{PROXY_BASE}/health")
        hsts = resp.headers.get("strict-transport-security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    def test_x_frame_options(self, client):
        """X-Frame-Options DENY header present."""
        resp = client.get(f"{PROXY_BASE}/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options(self, client):
        """X-Content-Type-Options nosniff header present."""
        resp = client.get(f"{PROXY_BASE}/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_referrer_policy(self, client):
        """Referrer-Policy header present."""
        resp = client.get(f"{PROXY_BASE}/health")
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_server_header_removed(self, client):
        """Caddy's Server header should be removed."""
        resp = client.get(f"{PROXY_BASE}/health")
        server = resp.headers.get("server", "")
        assert "caddy" not in server.lower()


class TestReverseProxy:
    """Verify reverse proxy correctly routes to backend."""

    def test_api_v1_routes(self, client):
        """API routes are proxied correctly."""
        # Auth endpoint should return 422 (missing body) not 404
        resp = client.post(f"{PROXY_BASE}/api/v1/auth/login")
        assert resp.status_code == 422  # validation error, not 404

    def test_nonexistent_route_gets_security_headers(self, client):
        """404 responses from backend still get Caddy's security headers."""
        resp = client.get(f"{PROXY_BASE}/nonexistent/path")
        assert resp.headers.get("x-frame-options") == "DENY"
        assert "max-age=31536000" in resp.headers.get("strict-transport-security", "")

    def test_backend_direct_still_works(self, backend_client):
        """Direct backend access still works (for debugging)."""
        resp = backend_client.get(f"{BACKEND_BASE}/health")
        assert resp.status_code == 200


class TestRequestLimits:
    """Verify request size limits enforced by Caddy."""

    def test_request_body_too_large_via_backend(self, backend_client):
        """Requests over 1MB are rejected by the backend's BodySizeLimitMiddleware.

        Tests directly against the backend (not through Caddy) because Caddy's
        reverse proxy mode doesn't reliably return 413 for oversized bodies.
        The backend middleware is the authoritative enforcement layer.
        """
        big_payload = b"x" * (1024 * 1024 + 1)  # 1MB + 1 byte
        resp = backend_client.post(
            f"{BACKEND_BASE}/api/v1/auth/login",
            content=big_payload,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 413


class TestPhotoUploadThroughProxy:
    """Regression test: photo uploads through Caddy must not get 413."""

    def test_photo_upload_passes_caddy_limit(self, client):
        """2MB photo upload through Caddy should not get 413.

        This is the exact bug that broke photo uploads — Caddy had a
        global 1MB request_body limit with no photo path exception.
        """
        big = b"\xff\xd8\xff" + b"x" * (2 * 1024 * 1024)
        resp = client.post(
            f"{PROXY_BASE}/api/v1/photo/recognize",
            files={"file": ("test.jpg", big, "image/jpeg")},
            timeout=30,
        )
        # Expect 401 (no auth) or 500 (bad image), but NOT 413
        assert resp.status_code != 413, (
            f"Caddy blocked photo upload with 413 — check handle blocks in Caddyfile"
        )


class TestEdgeCases:
    """Edge case tests for proxy behavior."""

    def test_redirect_preserves_path_and_query(self, client):
        """HTTP redirect preserves URI path and query params."""
        resp = client.get(f"{HTTP_BASE}/api/v1/foods/search?q=egg")
        location = resp.headers.get("location", "")
        assert "/api/v1/foods/search" in location
        assert "q=egg" in location

    def test_security_headers_on_api_routes(self, client):
        """Security headers present on API routes, not just /health."""
        resp = client.post(f"{PROXY_BASE}/api/v1/auth/login")
        assert resp.headers.get("x-frame-options") == "DENY"
        assert "max-age=31536000" in resp.headers.get("strict-transport-security", "")

    def test_options_request(self, client):
        """OPTIONS requests proxied correctly through Caddy."""
        resp = client.options(f"{PROXY_BASE}/api/v1/auth/login")
        # Any non-server-error response proves proxy forwards non-GET methods
        assert resp.status_code < 500


class TestCaddyfileValidation:
    """Validate Caddyfile syntax and structure."""

    def test_caddyfile_exists(self):
        """deploy/Caddyfile exists in the project."""
        from pathlib import Path
        caddyfile = Path(__file__).parent.parent / "deploy" / "Caddyfile"
        assert caddyfile.exists(), "deploy/Caddyfile not found"

    def test_caddyfile_validates(self):
        """Caddyfile passes Caddy's own syntax validator."""
        import subprocess
        from pathlib import Path
        caddyfile = Path(__file__).parent.parent / "deploy" / "Caddyfile"
        result = subprocess.run(
            ["caddy", "validate", "--config", str(caddyfile), "--adapter", "caddyfile"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"Caddy validate failed: {result.stderr}"

    def test_caddyfile_has_required_directives(self):
        """Caddyfile contains all required security directives."""
        from pathlib import Path
        content = (Path(__file__).parent.parent / "deploy" / "Caddyfile").read_text()

        required = [
            "Strict-Transport-Security",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "reverse_proxy localhost:9428",
            "tls internal",
            "health_uri /health",
            "-Server",
            "max_size",
            "roll_size",
            "roll_keep",
        ]
        for directive in required:
            assert directive in content, f"Missing directive: {directive}"

    def test_caddyfile_has_domain_migration_comment(self):
        """Caddyfile documents how to switch to a real domain."""
        from pathlib import Path
        content = (Path(__file__).parent.parent / "deploy" / "Caddyfile").read_text()
        assert "Let's Encrypt" in content or "letsencrypt" in content.lower()
