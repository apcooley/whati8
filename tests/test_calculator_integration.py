"""Integration tests verifying NutrientCalculator replaces old code paths correctly.

Step 2-3 of refactor: All nutrient computation goes through NutrientCalculator.
Tests verify that the API endpoints and daily log service produce correct results
using the new single code path.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from whati8.api.app import create_app
from whati8.api.deps import get_db
from whati8.models import Food, FoodNutrient, Nutrient, FoodPortion


@pytest.fixture
async def calc_client(db_session, seed_test_data, test_user):
    """Authenticated client for calculator integration tests."""
    app = create_app()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test/api/v1"
    ) as client:
        resp = await client.post(
            "/auth/login",
            json={"login": "testuser", "password": "testpassword123"},
        )
        client.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield client


@pytest.fixture
async def test_foods(db_session, seed_test_data, test_user):
    """Create test foods with known nutrients for integration testing."""
    energy = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Energy"))
    protein = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Protein"))
    fiber = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Fiber, total dietary"))
    fat = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Total lipid (fat)"))
    carbs = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Carbohydrate, by difference"))

    # Custom food: Protein Bar (200 cal, 20g protein per 60g bar)
    bar = Food(name="Test Protein Bar", serving_size=60, unit="g", created_by_user_id=test_user.id)
    db_session.add(bar)
    await db_session.flush()
    db_session.add(FoodNutrient(food_id=bar.id, nutrient_id=energy.id, amount_per_serving=200))
    db_session.add(FoodNutrient(food_id=bar.id, nutrient_id=protein.id, amount_per_serving=20))
    db_session.add(FoodNutrient(food_id=bar.id, nutrient_id=fat.id, amount_per_serving=7))
    db_session.add(FoodNutrient(food_id=bar.id, nutrient_id=fiber.id, amount_per_serving=3))
    db_session.add(FoodNutrient(food_id=bar.id, nutrient_id=carbs.id, amount_per_serving=22))
    db_session.add(FoodPortion(food_id=bar.id, amount=1, unit_name="bar", gram_weight=60,
                                portion_description="bar (60g)", sequence_number=1))
    db_session.add(FoodPortion(food_id=bar.id, amount=1, unit_name="g", gram_weight=1,
                                portion_description="grams", sequence_number=2))
    await db_session.flush()

    # USDA-style food: Apple (52 cal per 100g)
    apple = Food(name="Test Apple", serving_size=100, unit="g")
    db_session.add(apple)
    await db_session.flush()
    db_session.add(FoodNutrient(food_id=apple.id, nutrient_id=energy.id, amount_per_serving=52))
    db_session.add(FoodNutrient(food_id=apple.id, nutrient_id=protein.id, amount_per_serving=0.3))
    db_session.add(FoodNutrient(food_id=apple.id, nutrient_id=fiber.id, amount_per_serving=2.4))
    db_session.add(FoodNutrient(food_id=apple.id, nutrient_id=fat.id, amount_per_serving=0.2))
    db_session.add(FoodNutrient(food_id=apple.id, nutrient_id=carbs.id, amount_per_serving=13.8))
    await db_session.flush()

    return {"bar": bar, "apple": apple}


class TestFoodSummaryEndpoint:
    """GET /foods/{id}/summary should use NutrientCalculator."""

    @pytest.mark.asyncio
    async def test_summary_custom_food_one_serving(self, calc_client, test_foods):
        """Custom food at serving_size grams should return base nutrients."""
        bar = test_foods["bar"]
        resp = await calc_client.get(f"/foods/{bar.id}/summary?quantity=60")
        assert resp.status_code == 200
        data = resp.json()
        cal = next((d for d in data if d["name"] == "Calories"), None)
        assert cal is not None
        assert abs(cal["value"] - 200) < 1

    @pytest.mark.asyncio
    async def test_summary_custom_food_half_serving(self, calc_client, test_foods):
        """Half serving should halve the values."""
        bar = test_foods["bar"]
        resp = await calc_client.get(f"/foods/{bar.id}/summary?quantity=30")
        assert resp.status_code == 200
        data = resp.json()
        cal = next((d for d in data if d["name"] == "Calories"), None)
        assert abs(cal["value"] - 100) < 1

    @pytest.mark.asyncio
    async def test_summary_usda_food(self, calc_client, test_foods):
        """USDA food at 200g should double the per-100g values."""
        apple = test_foods["apple"]
        resp = await calc_client.get(f"/foods/{apple.id}/summary?quantity=200")
        assert resp.status_code == 200
        data = resp.json()
        cal = next((d for d in data if d["name"] == "Calories"), None)
        assert abs(cal["value"] - 104) < 1


class TestDailyLogSummary:
    """Daily log summary should use NutrientCalculator for totals."""

    @pytest.mark.asyncio
    async def test_daily_summary_matches_individual_logs(self, calc_client, test_foods):
        """Daily summary calories should equal sum of individual log calories."""
        bar = test_foods["bar"]
        apple = test_foods["apple"]

        # Log two foods
        from datetime import date
        today = date.today().isoformat()

        await calc_client.post("/logs", json={
            "food_id": bar.id, "quantity": 60, "unit": "grams",
            "logged_at": f"{today}T08:00:00",
        })
        await calc_client.post("/logs", json={
            "food_id": apple.id, "quantity": 200, "unit": "grams",
            "logged_at": f"{today}T12:00:00",
        })

        # Get daily view
        resp = await calc_client.get(f"/logs/daily/{today}")
        assert resp.status_code == 200
        data = resp.json()

        # Check summary totals
        summary = data.get("summary", {}).get("nutrients", [])
        cal = next((n for n in summary if n["name"] == "Calories"), None)
        assert cal is not None
        # Bar: 200 cal, Apple 200g: 104 cal, Total: 304
        assert abs(cal["value"] - 304) < 2

    @pytest.mark.asyncio
    async def test_per_log_summary_matches_food_summary(self, calc_client, test_foods):
        """Each log's summary_nutrients should match what /foods/{id}/summary returns."""
        bar = test_foods["bar"]
        from datetime import date
        today = date.today().isoformat()

        await calc_client.post("/logs", json={
            "food_id": bar.id, "quantity": 60, "unit": "grams",
            "logged_at": f"{today}T08:00:00",
        })

        # Get daily view
        resp = await calc_client.get(f"/logs/daily/{today}")
        data = resp.json()

        # Find the log's per-item summary
        log_cal = None
        for meal in data.get("meals", []):
            for log in meal.get("logs", []):
                if "Protein Bar" in log.get("food_name", ""):
                    sn = log.get("summary_nutrients", [])
                    log_cal = next((n for n in sn if n["name"] == "Calories"), None)

        # Also check ungrouped
        if log_cal is None:
            for log in data.get("ungrouped_logs", []):
                if "Protein Bar" in log.get("food_name", ""):
                    sn = log.get("summary_nutrients", [])
                    log_cal = next((n for n in sn if n["name"] == "Calories"), None)

        assert log_cal is not None, "Protein Bar log not found in daily view"
        assert abs(log_cal["value"] - 200) < 1
