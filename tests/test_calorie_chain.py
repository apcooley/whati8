"""End-to-end calorie accuracy tests.

Traces calories from input → storage → daily display → summary.
The system has ONE Energy nutrient (id=39, unit=kJ).
User inputs are in kcal. Conversion: 1 kcal = 4.184 kJ.

Test chain:
1. POST /foods/ with calories=140 kcal
2. Verify DB stores 140*4.184 = 585.76 kJ (or stores kcal with correct retrieval)  
3. GET /logs/daily/{date} → per-log calories = 140 kcal
4. Summary bar calories = 140 kcal
5. QuickLogSheet calorie estimate = 140 kcal
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date

from whati8.api.app import create_app
from whati8.models import Food, FoodPortion
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.nutrient import Nutrient


@pytest.fixture
async def client(db_session, seed_test_data, test_user):
    """Authenticated test client."""
    app = create_app()
    from whati8.api.deps import get_db
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/auth/login", json={
            "login": "testuser",
            "password": "testpassword123",
        })
        assert resp.status_code == 200
        ac.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield ac


class TestCalorieStorage:
    """Verify calories are stored correctly in the DB."""

    async def test_custom_food_energy_stored_correctly(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """When user enters 140 kcal, the stored value should produce 140 kcal on retrieval."""
        resp = await client.post("/foods/", json={
            "name": "Calorie Test Shake",
            "serving_size": 325,
            "unit": "bottle",
            "custom_unit": "bottle",
            "gram_weight": 325,
            "calories": 140,
            "protein": 30,
            "carbs": 7,
            "fat": 1.5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        # Check what's in the DB
        result = await db_session.execute(
            select(FoodNutrient, Nutrient)
            .join(Nutrient, FoodNutrient.nutrient_id == Nutrient.id)
            .where(FoodNutrient.food_id == food_id)
            .where(Nutrient.name == "Energy")
        )
        row = result.first()
        assert row is not None, "No Energy nutrient found for food"
        fn, nutrient = row

        stored_value = float(fn.amount_per_serving)

        if nutrient.unit == "kJ":
            # If stored as kJ, value should be kcal * 4.184
            expected_kj = 140 * 4.184
            assert abs(stored_value - expected_kj) < 1.0, (
                f"Stored {stored_value} kJ, expected {expected_kj} kJ (140 kcal * 4.184)"
            )
        elif nutrient.unit == "kcal":
            assert stored_value == 140.0
        else:
            pytest.fail(f"Unexpected energy unit: {nutrient.unit}")


class TestCalorieRetrieval:
    """Verify calories display correctly through the full chain."""

    async def test_daily_log_shows_correct_kcal(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Create 140kcal food → log it → daily view shows 140 kcal."""
        # Create food
        resp = await client.post("/foods/", json={
            "name": "Daily Cal Test",
            "serving_size": 100,
            "unit": "g",
            "calories": 200,
            "protein": 10,
            "carbs": 20,
            "fat": 5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        # Register
        resp = await client.post("/profile/foods/register", json={
            "food_id": food_id,
            "default_quantity": 1,
            "default_unit": "grams",
        })
        assert resp.status_code == 201
        uf_id = resp.json()["id"]

        # Log 100g
        resp = await client.post("/logs/quick", json={
            "user_food_id": uf_id,
            "quantity": 100,
            "unit": "grams",
        })
        assert resp.status_code in (200, 201), f"Log failed: {resp.text}"

        # Check daily
        today = date.today().isoformat()
        resp = await client.get(f"/logs/daily/{today}")
        assert resp.status_code == 200
        daily = resp.json()

        all_logs = [l for m in daily["meals"] for l in m["logs"]]
        our_log = [l for l in all_logs if l["food_name"] == "Daily Cal Test"]
        assert len(our_log) >= 1

        log_cal = our_log[0]["calories"]
        assert log_cal is not None, "Calories is None in daily log"
        # Should be 200 kcal (not 200/4.184=47.8, and not 200*4.184=836.8)
        assert 190 < log_cal < 210, f"Expected ~200 kcal, got {log_cal}"

    async def test_summary_shows_correct_total(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Summary bar total should match sum of per-log calories."""
        # Create two foods
        for name, cal in [("Sum Food A", 100), ("Sum Food B", 250)]:
            resp = await client.post("/foods/", json={
                "name": name, "serving_size": 50, "unit": "g",
                "calories": cal, "protein": 5, "carbs": 10, "fat": 3,
            })
            assert resp.status_code == 200
            food_id = resp.json()["id"]

            resp = await client.post("/profile/foods/register", json={
                "food_id": food_id, "default_quantity": 1, "default_unit": "grams",
            })
            assert resp.status_code == 201
            uf_id = resp.json()["id"]

            resp = await client.post("/logs/quick", json={
                "user_food_id": uf_id, "quantity": 50, "unit": "grams",
            })
            assert resp.status_code in (200, 201)

        today = date.today().isoformat()
        resp = await client.get(f"/logs/daily/{today}")
        assert resp.status_code == 200
        daily = resp.json()

        # Sum per-log calories
        all_logs = [l for m in daily["meals"] for l in m["logs"]]
        log_total = sum(l["calories"] for l in all_logs if l["calories"])

        # Get summary calories
        summary_cals = [n for n in daily["summary"]["nutrients"] if "cal" in n["name"].lower()]
        if summary_cals:
            summary_val = summary_cals[0]["value"]
            if summary_val > 0:  # Only check if summary config exists for user
                assert abs(log_total - summary_val) < 2.0, (
                    f"Log total {log_total} != summary {summary_val}"
                )
        # At minimum, verify log totals are reasonable
        assert log_total == 350.0, f"Expected 350 kcal total, got {log_total}"


class TestCalorieWithPortions:
    """Verify calories scale correctly with different portion sizes."""

    async def test_custom_unit_calories(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """1 bottle (325g) of 140kcal food → daily shows 140 kcal."""
        resp = await client.post("/foods/", json={
            "name": "Portion Cal Test",
            "serving_size": 325,
            "unit": "bottle",
            "custom_unit": "bottle",
            "gram_weight": 325,
            "serving_description": "1 bottle (325g)",
            "calories": 140,
            "protein": 30,
            "carbs": 7,
            "fat": 1.5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        resp = await client.post("/profile/foods/register", json={
            "food_id": food_id, "default_quantity": 1,
            "default_unit": "1 bottle (325g)",
        })
        assert resp.status_code == 201
        uf_id = resp.json()["id"]

        resp = await client.post("/logs/quick", json={
            "user_food_id": uf_id, "quantity": 1,
            "unit": "1 bottle (325g)",
        })
        assert resp.status_code in (200, 201)

        today = date.today().isoformat()
        resp = await client.get(f"/logs/daily/{today}")
        assert resp.status_code == 200

        all_logs = [l for m in resp.json()["meals"] for l in m["logs"]]
        our = [l for l in all_logs if l["food_name"] == "Portion Cal Test"]
        assert len(our) >= 1

        cal = our[0]["calories"]
        assert cal is not None
        # Should be 140 kcal, not 33 (=140/4.184) or 585 (=140*4.184)
        assert 130 < cal < 150, f"Expected ~140 kcal, got {cal}"
