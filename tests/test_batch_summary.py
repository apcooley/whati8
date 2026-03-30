"""Tests for batch summary endpoint and config caching.

Validates:
- POST /api/v1/foods/batch-summary returns correct summaries
- Batch results match individual endpoint results
- Empty batch returns empty dict
- Over-limit batch returns 400
- Auth required
- Frontend batch module exists
- FoodSummary component uses batched fetcher
"""

import pytest
import httpx

SERVER = "http://localhost:9428"
TEST_USER = "testbot"
TEST_PASS = "testbot123"

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def token():
    r = httpx.post(f"{SERVER}/api/v1/auth/login", json={"login": TEST_USER, "password": TEST_PASS})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


class TestBatchSummaryEndpoint:
    """POST /api/v1/foods/batch-summary"""

    def test_batch_returns_summaries(self, auth_headers):
        """Batch endpoint returns summary data for multiple foods."""
        r = httpx.post(
            f"{SERVER}/api/v1/foods/batch-summary",
            json={"items": [
                {"food_id": 1, "quantity": 100},
                {"food_id": 2, "quantity": 200},
            ]},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)
        # Should have keys like "1:100" and "2:200"
        assert len(data) > 0

    def test_batch_matches_individual(self, auth_headers):
        """Batch results must match individual /foods/{id}/summary results."""
        food_id = 1
        quantity = 150

        # Individual call
        individual = httpx.get(
            f"{SERVER}/api/v1/foods/{food_id}/summary?quantity={quantity}",
            headers=auth_headers,
            timeout=30,
        )
        assert individual.status_code == 200

        # Batch call
        batch = httpx.post(
            f"{SERVER}/api/v1/foods/batch-summary",
            json={"items": [{"food_id": food_id, "quantity": quantity}]},
            headers=auth_headers,
            timeout=30,
        )
        assert batch.status_code == 200

        individual_data = individual.json()
        batch_data = batch.json()
        key = f"{food_id}:{quantity}"
        assert key in batch_data

        # Compare nutrient values
        batch_nutrients = batch_data[key]
        assert len(batch_nutrients) == len(individual_data)
        for i, nutrient in enumerate(individual_data):
            assert batch_nutrients[i]["name"] == nutrient["name"]
            assert abs(batch_nutrients[i]["value"] - nutrient["value"]) < 0.01

    def test_empty_batch_returns_empty(self, auth_headers):
        """Empty items list returns empty dict."""
        r = httpx.post(
            f"{SERVER}/api/v1/foods/batch-summary",
            json={"items": []},
            headers=auth_headers,
            timeout=10,
        )
        assert r.status_code == 200
        assert r.json() == {}

    def test_batch_over_limit_returns_400(self, auth_headers):
        """More than 50 items should return 400."""
        items = [{"food_id": 1, "quantity": 100}] * 51
        r = httpx.post(
            f"{SERVER}/api/v1/foods/batch-summary",
            json={"items": items},
            headers=auth_headers,
            timeout=10,
        )
        assert r.status_code == 400

    def test_batch_requires_auth(self):
        """Batch endpoint requires authentication."""
        r = httpx.post(
            f"{SERVER}/api/v1/foods/batch-summary",
            json={"items": [{"food_id": 1, "quantity": 100}]},
            timeout=10,
        )
        assert r.status_code == 401

    def test_nonexistent_food_skipped(self, auth_headers):
        """Non-existent food IDs are silently skipped."""
        r = httpx.post(
            f"{SERVER}/api/v1/foods/batch-summary",
            json={"items": [
                {"food_id": 999999, "quantity": 100},
                {"food_id": 1, "quantity": 100},
            ]},
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert "999999:100" not in data  # skipped
        assert "1:100.0" in data or "1:100" in data  # present

    def test_batch_performance(self, auth_headers):
        """10 items should complete in under 2 seconds."""
        import time
        items = [{"food_id": i, "quantity": 100} for i in range(1, 11)]
        start = time.time()
        r = httpx.post(
            f"{SERVER}/api/v1/foods/batch-summary",
            json={"items": items},
            headers=auth_headers,
            timeout=30,
        )
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 2.0, f"Batch took {elapsed:.1f}s — must be under 2s"


class TestFrontendBatchIntegration:
    """Verify frontend uses the batch fetcher."""

    def test_summary_batch_module_exists(self):
        """summaryBatch.ts must exist."""
        from pathlib import Path
        path = Path(__file__).parent.parent / "frontend" / "src" / "lib" / "api" / "summaryBatch.ts"
        assert path.exists(), "frontend/src/lib/api/summaryBatch.ts not found"

    def test_food_summary_uses_batched(self):
        """FoodSummary.svelte must import from summaryBatch."""
        from pathlib import Path
        path = Path(__file__).parent.parent / "frontend" / "src" / "lib" / "components" / "FoodSummary.svelte"
        content = path.read_text()
        assert "summaryBatch" in content, (
            "FoodSummary.svelte must use the batched summary fetcher"
        )

    def test_batch_endpoint_in_foods_api(self):
        """foods.ts must export getBatchFoodSummary."""
        from pathlib import Path
        path = Path(__file__).parent.parent / "frontend" / "src" / "lib" / "api" / "foods.ts"
        content = path.read_text()
        assert "getBatchFoodSummary" in content or "batch-summary" in content, (
            "foods.ts must have a batch summary function"
        )

    def test_frontend_build_has_batch(self):
        """Built frontend JS must contain batch-summary endpoint."""
        from pathlib import Path
        dist = Path(__file__).parent.parent / "frontend" / "dist" / "assets"
        if not dist.exists():
            pytest.skip("Frontend not built")
        js_files = list(dist.glob("*.js"))
        combined = "".join(f.read_text() for f in js_files)
        assert "batch-summary" in combined, (
            "Frontend build must reference batch-summary endpoint — rebuild with: cd frontend && npm run build"
        )
