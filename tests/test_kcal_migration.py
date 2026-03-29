"""Tests for kcal migration — Energy nutrient should store kcal, not kJ.

After migration:
1. Nutrient 39 unit = "kcal" (not "kJ")
2. All USDA foods have kcal values in nutrient 39
3. All custom foods have kcal values in nutrient 39
4. No kJ→kcal conversion anywhere in the display chain
5. Custom food creation stores kcal directly (no * 4.184)
6. Daily log calorie display = raw amount_per_serving scaled by portion
7. Recipe materialization stores kcal
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.app import create_app
from whati8.models import Food, FoodPortion
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.nutrient import Nutrient


@pytest.fixture
async def client(db_session, seed_test_data, test_user):
    app = create_app()
    from whati8.api.deps import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        resp = await ac.post("/auth/login", json={
            "login": "testuser", "password": "testpassword123",
        })
        assert resp.status_code == 200
        ac.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield ac


@pytest.fixture
async def energy_nutrient(db_session: AsyncSession, seed_test_data) -> Nutrient:
    """Get the Energy nutrient — should be kcal after migration."""
    n = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Energy"))
    assert n is not None
    return n


class TestEnergyNutrientUnit:
    """Nutrient 39 should be in kcal."""

    async def test_energy_unit_is_kcal(self, energy_nutrient: Nutrient):
        """Energy nutrient unit must be 'kcal', not 'kJ'."""
        assert energy_nutrient.unit == "kcal", (
            f"Energy unit is '{energy_nutrient.unit}', expected 'kcal'"
        )


class TestCustomFoodCreation:
    """Custom foods should store kcal directly, no conversion."""

    async def test_create_food_stores_kcal_directly(
        self, client: AsyncClient, db_session: AsyncSession, energy_nutrient
    ):
        """POST /foods/ with calories=200 → stores 200 in DB (not 200*4.184)."""
        resp = await client.post("/foods/", json={
            "name": "Kcal Test Food",
            "serving_size": 100, "unit": "g",
            "calories": 200, "protein": 10, "carbs": 20, "fat": 5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodNutrient)
            .where(FoodNutrient.food_id == food_id, FoodNutrient.nutrient_id == energy_nutrient.id)
        )
        fn = result.scalar_one()
        stored = float(fn.amount_per_serving)

        # Should be 200, NOT 200*4.184=836.8
        assert abs(stored - 200) < 0.1, (
            f"Stored {stored}, expected 200 (got multiplied by 4.184?)"
        )

    async def test_create_food_140_kcal_stores_140(
        self, client: AsyncClient, db_session: AsyncSession, energy_nutrient
    ):
        """The protein shake scenario: 140 kcal should store as 140."""
        resp = await client.post("/foods/", json={
            "name": "Protein Shake Test",
            "serving_size": 325, "unit": "bottle",
            "custom_unit": "bottle", "gram_weight": 325,
            "calories": 140, "protein": 30, "carbs": 7, "fat": 1.5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodNutrient)
            .where(FoodNutrient.food_id == food_id, FoodNutrient.nutrient_id == energy_nutrient.id)
        )
        fn = result.scalar_one()
        assert abs(float(fn.amount_per_serving) - 140) < 0.1


class TestDailyLogCalories:
    """Daily log should show calories without any kJ conversion."""

    async def test_usda_food_calories_correct(
        self, client: AsyncClient, db_session: AsyncSession, energy_nutrient
    ):
        """USDA food with 273 kcal/100g logged as 43g → 117 kcal."""
        # Create USDA-like food (no created_by_user_id)
        food = Food(name="Test Bun", serving_size=43, unit="g", created_by_user_id=None)
        db_session.add(food)
        await db_session.flush()
        db_session.add(FoodNutrient(food_id=food.id, nutrient_id=energy_nutrient.id, amount_per_serving=273))
        db_session.add(FoodPortion(
            food_id=food.id, amount=1, unit_name="serving",
            gram_weight=43, portion_description="serving (43g)", sequence_number=1,
        ))
        db_session.add(FoodPortion(
            food_id=food.id, amount=1, unit_name="g",
            gram_weight=1, portion_description="grams", sequence_number=2,
        ))
        await db_session.commit()

        # Register and log
        resp = await client.post("/profile/foods/register", json={
            "food_id": food.id, "default_quantity": 1, "default_unit": "serving (43g)",
        })
        assert resp.status_code == 201
        uf_id = resp.json()["id"]

        resp = await client.post("/logs/quick", json={
            "user_food_id": uf_id, "quantity": 1, "unit": "serving (43g)",
        })
        assert resp.status_code in (200, 201)

        # Check daily
        from datetime import date
        today = date.today().isoformat()
        resp = await client.get(f"/logs/daily/{today}")
        assert resp.status_code == 200
        
        all_logs = [l for m in resp.json()["meals"] for l in m["logs"]]
        bun_log = [l for l in all_logs if l["food_name"] == "Test Bun"]
        assert len(bun_log) >= 1

        cal = bun_log[0]["calories"]
        assert cal is not None
        # 273 kcal/100g * 43g/100 = 117.4 kcal
        # NOT 273/4.184 * 43/100 = 28 kcal (the old bug)
        assert abs(cal - 117.4) < 2, f"Expected ~117 kcal, got {cal}"

    async def test_custom_food_calories_correct(
        self, client: AsyncClient, db_session: AsyncSession, energy_nutrient
    ):
        """Custom food with 140 kcal per 325g serving → log shows 140 kcal."""
        resp = await client.post("/foods/", json={
            "name": "Cal Display Test",
            "serving_size": 325, "unit": "bottle",
            "custom_unit": "bottle", "gram_weight": 325,
            "calories": 140, "protein": 30, "carbs": 7, "fat": 1.5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        resp = await client.post("/profile/foods/register", json={
            "food_id": food_id, "default_quantity": 1, "default_unit": "bottle (325g)",
        })
        assert resp.status_code == 201
        uf_id = resp.json()["id"]

        resp = await client.post("/logs/quick", json={
            "user_food_id": uf_id, "quantity": 1, "unit": "bottle (325g)",
        })
        assert resp.status_code in (200, 201)

        from datetime import date
        today = date.today().isoformat()
        resp = await client.get(f"/logs/daily/{today}")
        assert resp.status_code == 200

        all_logs = [l for m in resp.json()["meals"] for l in m["logs"]]
        shake = [l for l in all_logs if l["food_name"] == "Cal Display Test"]
        assert len(shake) >= 1

        cal = shake[0]["calories"]
        assert cal is not None
        assert abs(cal - 140) < 2, f"Expected ~140 kcal, got {cal}"

    async def test_grams_logging_correct(
        self, client: AsyncClient, db_session: AsyncSession, energy_nutrient
    ):
        """100g of a 200 kcal/100g food → 200 kcal."""
        resp = await client.post("/foods/", json={
            "name": "Grams Cal Test",
            "serving_size": 100, "unit": "g",
            "calories": 200, "protein": 10, "carbs": 20, "fat": 5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        resp = await client.post("/profile/foods/register", json={
            "food_id": food_id, "default_quantity": 100, "default_unit": "grams",
        })
        assert resp.status_code == 201
        uf_id = resp.json()["id"]

        resp = await client.post("/logs/quick", json={
            "user_food_id": uf_id, "quantity": 100, "unit": "grams",
        })
        assert resp.status_code in (200, 201)

        from datetime import date
        resp = await client.get(f"/logs/daily/{date.today().isoformat()}")
        all_logs = [l for m in resp.json()["meals"] for l in m["logs"]]
        test_log = [l for l in all_logs if l["food_name"] == "Grams Cal Test"]
        assert len(test_log) >= 1
        assert abs(test_log[0]["calories"] - 200) < 2


class TestNoKjConversionInCode:
    """Verify no kJ→kcal conversion code remains in the calorie display path."""

    async def test_no_kj_division_in_daily_log_service(self):
        """The daily log service should not divide energy by 4.184."""
        import inspect
        from whati8.services.daily_log_service import DailyLogService
        
        source = inspect.getsource(DailyLogService.get_daily_logs)
        # Should NOT have / 4.184 or /4.184 for energy conversion
        assert "/ 4.184" not in source and "/4.184" not in source, (
            "daily_log_service still has kJ→kcal conversion code (/ 4.184)"
        )

    async def test_no_kj_conversion_in_food_creation(self):
        """Food creation should not multiply calories by 4.184."""
        with open("whati8/api/routers/food.py") as f:
            source = f.read()
        
        # The kcal→kJ conversion we added should be removed
        assert "* 4.184" not in source, (
            "food.py still has kcal→kJ conversion (* 4.184)"
        )

    async def test_no_kj_conversion_in_portion_scale(self):
        """_portion_scale should not reference kJ."""
        import inspect
        from whati8.services.daily_log_service import _portion_scale
        source = inspect.getsource(_portion_scale)
        assert "4.184" not in source


class TestRecipeMaterialization:
    """Recipe nutrition should use kcal directly."""

    async def test_recipe_stores_kcal(
        self, client: AsyncClient, db_session: AsyncSession, energy_nutrient
    ):
        """Recipe materialized food should have kcal energy values."""
        # Create ingredient food
        resp = await client.post("/foods/", json={
            "name": "Recipe Ingredient",
            "serving_size": 100, "unit": "g",
            "calories": 300, "protein": 15, "carbs": 40, "fat": 10,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        # Create recipe
        resp = await client.post("/recipes/", json={
            "name": "Kcal Recipe Test",
            "servings": 2, "serving_unit": "serving",
            "ingredients": [
                {"food_id": food_id, "quantity": 200, "unit": "grams", "portion_description": "grams"},
            ],
        })
        assert resp.status_code == 200
        recipe_food_id = resp.json()["food_id"]

        # Check the materialized food's energy
        result = await db_session.execute(
            select(FoodNutrient)
            .where(FoodNutrient.food_id == recipe_food_id, FoodNutrient.nutrient_id == energy_nutrient.id)
        )
        fn = result.scalar_one()
        stored = float(fn.amount_per_serving)

        # 200g of 300 kcal/100g = 600 kcal total / 2 servings = 300 kcal per serving
        assert abs(stored - 300) < 2, f"Recipe energy: {stored}, expected 300 kcal"
