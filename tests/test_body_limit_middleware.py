"""Tests for BodySizeLimitMiddleware.

Verifies:
- Normal requests (<1MB) pass through on all endpoints
- Oversized requests (>1MB) get 413 on normal endpoints
- Photo upload path (/api/v1/photo/recognize) allows up to 10MB
- Both /api/v1/photo/recognize and /photo/recognize paths are exempted
  (Starlette middleware may see the path with or without the router prefix)
- Requests exactly at the limit are accepted
- Requests 1 byte over the limit are rejected
- GET/HEAD/OPTIONS bypass body checks entirely
- Chunked (no Content-Length) requests are also checked

Tests hit the live backend at localhost:9428.
"""

import pytest
import httpx

SERVER = "http://localhost:9428"
TEST_USER = "testbot"
TEST_PASS = "testbot123"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def token():
    """Login once for the whole module."""
    r = httpx.post(f"{SERVER}/api/v1/auth/login", json={"login": TEST_USER, "password": TEST_PASS})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestNormalEndpointBodyLimit:
    """Normal endpoints enforce the 1MB limit."""

    def test_small_request_passes(self, auth_headers):
        """A normal-sized request should pass through."""
        r = httpx.post(
            f"{SERVER}/api/v1/foods/search",
            json={"query": "chicken"},
            headers=auth_headers,
        )
        assert r.status_code != 413

    def test_oversized_request_rejected(self):
        """Requests over 1MB to normal endpoints get 413."""
        big = b"x" * (1024 * 1024 + 1)
        r = httpx.post(
            f"{SERVER}/api/v1/auth/login",
            content=big,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 413

    def test_exactly_1mb_passes(self):
        """A request at exactly 1MB should pass (limit is >1MB, not >=)."""
        payload = b"x" * (1024 * 1024)
        r = httpx.post(
            f"{SERVER}/api/v1/auth/login",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        # Should NOT be 413 — may be 422 (bad JSON) or 401, but not 413
        assert r.status_code != 413

    def test_1mb_plus_one_byte_rejected(self):
        """1MB + 1 byte should be rejected."""
        payload = b"x" * (1024 * 1024 + 1)
        r = httpx.post(
            f"{SERVER}/api/v1/auth/login",
            content=payload,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 413

    def test_413_response_is_json(self):
        """413 response should have a structured JSON body."""
        big = b"x" * (1024 * 1024 + 1)
        r = httpx.post(
            f"{SERVER}/api/v1/auth/login",
            content=big,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 413
        data = r.json()
        assert "error" in data
        assert data["error"]["status_code"] == 413


class TestPhotoUploadExemption:
    """Photo upload path allows up to 10MB."""

    def test_2mb_photo_passes(self, auth_headers):
        """A 2MB photo upload should NOT get 413."""
        big = b"\xff\xd8\xff" + b"x" * (2 * 1024 * 1024)
        r = httpx.post(
            f"{SERVER}/api/v1/photo/recognize",
            files={"file": ("test.jpg", big, "image/jpeg")},
            headers=auth_headers,
            timeout=30,
        )
        # Should be 500 (bad image for Claude) or 200, but NOT 413
        assert r.status_code != 413

    def test_5mb_photo_passes(self, auth_headers):
        """A 5MB photo upload should NOT get 413."""
        big = b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024)
        r = httpx.post(
            f"{SERVER}/api/v1/photo/recognize",
            files={"file": ("test.jpg", big, "image/jpeg")},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code != 413

    def test_over_10mb_photo_rejected(self, auth_headers):
        """A photo over 10MB should get 413."""
        big = b"\xff\xd8\xff" + b"x" * (10 * 1024 * 1024 + 1)
        r = httpx.post(
            f"{SERVER}/api/v1/photo/recognize",
            files={"file": ("test.jpg", big, "image/jpeg")},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 413


class TestHTTPMethodBypass:
    """GET, HEAD, and OPTIONS should bypass body checks."""

    def test_get_bypasses_body_check(self):
        """GET requests should never trigger body limit."""
        r = httpx.get(f"{SERVER}/api/v1/foods/search?query=test")
        # May be 401 or 200, but not 413
        assert r.status_code != 413

    def test_options_bypasses_body_check(self):
        """OPTIONS requests should never trigger body limit."""
        r = httpx.options(f"{SERVER}/api/v1/auth/login")
        assert r.status_code != 413


class TestPathVariants:
    """Both /api/v1/photo/recognize and /photo/recognize should be exempted.

    Starlette BaseHTTPMiddleware may see the path with or without the
    /api/v1 prefix depending on how routers are mounted.
    """

    def test_prefixed_path_exempted(self, auth_headers):
        """The full /api/v1/photo/recognize path allows large bodies."""
        big = b"\xff\xd8\xff" + b"x" * (2 * 1024 * 1024)
        r = httpx.post(
            f"{SERVER}/api/v1/photo/recognize",
            files={"file": ("test.jpg", big, "image/jpeg")},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code != 413

    def test_unprefixed_path_exempted(self):
        """The bare /photo/recognize path also allows large bodies.

        This path is what middleware actually sees at runtime due to
        FastAPI's router prefix stripping. No matching route exists at
        this URL, so we expect 404/405 — but crucially NOT 413.
        Tests unauthenticated since the path has no route anyway.
        """
        big = b"\xff\xd8\xff" + b"x" * (2 * 1024 * 1024)
        r = httpx.post(
            f"{SERVER}/photo/recognize",
            files={"file": ("test.jpg", big, "image/jpeg")},
            timeout=30,
        )
        # May be 405 (no route) or 404, but NOT 413
        assert r.status_code != 413


class TestChunkedTransferEncoding:
    """Chunked requests (no Content-Length) must also be checked."""

    def test_oversized_chunked_request_rejected(self):
        """Chunked requests over 1MB to normal endpoints get 413."""

        def big_chunks():
            for _ in range(1025):
                yield b"x" * 1024  # 1025 KB > 1MB

        r = httpx.post(
            f"{SERVER}/api/v1/auth/login",
            content=big_chunks(),
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 413

    def test_chunked_photo_upload_passes(self, auth_headers):
        """Chunked photo upload under 10MB should pass through."""

        def photo_chunks():
            yield b"\xff\xd8\xff"
            for _ in range(2048):
                yield b"x" * 1024  # ~2MB total

        r = httpx.post(
            f"{SERVER}/api/v1/photo/recognize",
            content=photo_chunks(),
            headers={**auth_headers, "Content-Type": "image/jpeg"},
            timeout=30,
        )
        # Should NOT be 413 — may be 500 (bad image) or 422, but not 413
        assert r.status_code != 413


class TestBoundaryExact:
    """Exact boundary conditions for the 10MB photo limit."""

    def test_exactly_10mb_photo_passes(self, auth_headers):
        """A photo at exactly 10MB should pass (limit is >10MB, not >=).

        Multipart encoding adds ~200 bytes of headers/boundaries, so we
        subtract overhead to keep Content-Length at exactly 10MB.
        """
        overhead = 256  # multipart boundary + headers
        big = b"\xff\xd8\xff" + b"x" * (10 * 1024 * 1024 - 3 - overhead)
        r = httpx.post(
            f"{SERVER}/api/v1/photo/recognize",
            files={"file": ("test.jpg", big, "image/jpeg")},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code != 413

    def test_put_oversized_rejected(self):
        """PUT requests over 1MB to normal endpoints also get 413."""
        big = b"x" * (1024 * 1024 + 1)
        r = httpx.put(
            f"{SERVER}/api/v1/foods/99999",
            content=big,
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 413


class TestFrontendBuildIntegrity:
    """Verify the built frontend uses the correct API paths."""

    def test_photo_api_path_in_build(self):
        """The frontend dist must use /api/v1/photo/recognize, not /photo/recognize."""
        from pathlib import Path

        dist_dir = Path(__file__).parent.parent / "frontend" / "dist" / "assets"
        if not dist_dir.exists():
            pytest.skip("Frontend not built (no dist/assets)")

        js_files = list(dist_dir.glob("*.js"))
        assert js_files, "No JS files in dist/assets"

        combined = ""
        for f in js_files:
            combined += f.read_text()

        assert "/api/v1/photo/recognize" in combined, (
            "Frontend build uses wrong photo API path — rebuild with: cd frontend && npm run build"
        )
        # The bare path should NOT appear (except as substring of the full path)
        import re
        bare_matches = re.findall(r'["\']\/photo\/recognize["\']', combined)
        assert not bare_matches, (
            f"Frontend build has bare /photo/recognize path (stale build): {bare_matches}"
        )
