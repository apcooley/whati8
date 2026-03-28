"""Tests for photo-based food creation and registration flow.

Tests the full pipeline:
1. POST /foods/ — create custom food with various serving types
2. Verify portions are created correctly for each type
3. POST /profile/foods/register — register to user profile
4. Verify calorie calculations via daily log service
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.app import create_app
from whati8.models import FoodPortion
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.nutrient import Nutrient


@pytest.fixture
async def client(db_session, seed_test_data, test_user):
    """Create authenticated test client."""
    app = create_app()

    from whati8.api.deps import get_db
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as ac:
        resp = await ac.post("/auth/login", json={
            "login": "testuser",
            "password": "testpassword123",
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        token = resp.json()["access_token"]
        ac.headers["Authorization"] = f"Bearer {token}"
        yield ac


class TestCreateCustomFood:
    """Test POST /foods/ with different serving types."""

    async def test_weight_only(self, client: AsyncClient, db_session: AsyncSession):
        """Type 1: Weight-based serving (e.g. 40g oats)."""
        resp = await client.post("/foods/", json={
            "name": "Steel Cut Oats",
            "serving_size": 40,
            "unit": "g",
            "calories": 150,
            "protein": 5,
            "carbs": 27,
            "fat": 2.5,
            "fiber": 4,
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        portions = result.scalars().all()
        labels = {p.portion_description for p in portions}

        assert "grams" in labels, f"Missing grams. Got: {labels}"
        assert "oz" in labels, f"Missing oz. Got: {labels}"
        assert len(portions) >= 2

    async def test_custom_unit_with_weight(self, client: AsyncClient, db_session: AsyncSession):
        """Type 3: Custom unit + weight (e.g. 1 bar = 60g)."""
        resp = await client.post("/foods/", json={
            "name": "Protein Bar",
            "serving_size": 60,
            "unit": "bar",
            "custom_unit": "bar",
            "gram_weight": 60,
            "serving_description": "1 bar (60g)",
            "calories": 200,
            "protein": 20,
            "carbs": 22,
            "fat": 7,
            "fiber": 3,
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        portions = result.scalars().all()
        pm = {p.unit_name: p for p in portions}

        assert "bar" in pm, f"Missing 'bar'. Got: {list(pm.keys())}"
        assert pm["bar"].gram_weight == 60.0
        assert pm["bar"].portion_description == "bar (60g)"
        assert "g" in pm
        assert pm["g"].gram_weight == 1.0
        assert "oz" in pm
        assert "fl oz" not in pm
        assert "mL" not in pm

    async def test_custom_unit_with_volume(self, client: AsyncClient, db_session: AsyncSession):
        """Type 4: Custom unit + volume (e.g. 1 bottle, 325mL, 325g)."""
        resp = await client.post("/foods/", json={
            "name": "Protein Shake",
            "serving_size": 325,
            "unit": "bottle",
            "custom_unit": "bottle",
            "gram_weight": 325,
            "volume_ml": 325,
            "serving_description": "1 bottle (325 mL, 325g)",
            "calories": 140,
            "protein": 30,
            "carbs": 7,
            "fat": 1.5,
            "fiber": 4,
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        portions = result.scalars().all()
        pm = {p.unit_name: p for p in portions}

        assert "bottle" in pm, f"Missing 'bottle'. Got: {list(pm.keys())}"
        assert float(pm["bottle"].gram_weight) == 325.0  # 1 bottle = 325g

        assert "fl oz" in pm, f"Missing 'fl oz'. Got: {list(pm.keys())}"
        assert abs(float(pm["fl oz"].gram_weight) - 29.57) < 0.1

        assert "mL" in pm
        assert abs(float(pm["mL"].gram_weight) - 1.0) < 0.01

        assert "g" in pm
        assert "oz" in pm

    async def test_density_calculation(self, client: AsyncClient, db_session: AsyncSession):
        """Volume portions use density correctly for non-water liquids."""
        resp = await client.post("/foods/", json={
            "name": "Honey Drink",
            "serving_size": 350,
            "unit": "bottle",
            "custom_unit": "bottle",
            "gram_weight": 350,
            "volume_ml": 250,
            "serving_description": "1 bottle (250 mL, 350g)",
            "calories": 200,
            "protein": 0,
            "carbs": 50,
            "fat": 0,
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        pm = {p.unit_name: p for p in result.scalars().all()}

        # density = 350/250 = 1.4 g/mL → fl oz = 1.4 * 29.57 = 41.4g
        assert abs(float(pm["fl oz"].gram_weight) - 41.4) < 0.2
        assert abs(float(pm["mL"].gram_weight) - 1.4) < 0.01


    async def test_multi_unit_serving(self, client: AsyncClient, db_session: AsyncSession):
        """Type 3 with quantity: 6 crackers = 28g → 1 cracker = 4.67g."""
        resp = await client.post("/foods/", json={
            "name": "Triscuit Crackers",
            "serving_size": 28,
            "unit": "crackers",
            "custom_unit": "crackers",
            "gram_weight": 28,
            "serving_quantity": 6,
            "serving_description": "crackers (5g)",
            "calories": 120,
            "protein": 3,
            "carbs": 20,
            "fat": 4,
            "fiber": 3,
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        pm = {p.unit_name: p for p in result.scalars().all()}

        assert "crackers" in pm
        # gram_weight should be per 1 cracker: 28/6 = 4.67g
        assert abs(float(pm["crackers"].gram_weight) - 4.67) < 0.1, (
            f"Expected ~4.67g per cracker, got {pm['crackers'].gram_weight}"
        )
        # amount should be 6 (serving quantity)
        assert float(pm["crackers"].amount) == 6.0
    async def test_nutrients_stored(self, client: AsyncClient, db_session: AsyncSession):
        """Verify nutrient values match input."""
        resp = await client.post("/foods/", json={
            "name": "Nutrient Check",
            "serving_size": 100,
            "unit": "g",
            "calories": 250,
            "protein": 15,
            "carbs": 30,
            "fat": 8,
            "fiber": 5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodNutrient, Nutrient)
            .join(Nutrient, FoodNutrient.nutrient_id == Nutrient.id)
            .where(FoodNutrient.food_id == food_id)
        )
        nv = {n.name: float(fn.amount_per_serving) for fn, n in result.all()}

        assert nv.get("Energy") == 250.0
        assert nv.get("Protein") == 15.0
        assert nv.get("Carbohydrate, by difference") == 30.0
        assert nv.get("Total lipid (fat)") == 8.0
        assert nv.get("Fiber, total dietary") == 5.0

    async def test_missing_name_422(self, client: AsyncClient):
        """Missing 'name' returns 422."""
        resp = await client.post("/foods/", json={
            "serving_size": 100, "unit": "g", "calories": 50,
        })
        assert resp.status_code == 422

    async def test_missing_calories_422(self, client: AsyncClient):
        """Missing 'calories' returns 422."""
        resp = await client.post("/foods/", json={
            "name": "Bad", "serving_size": 100, "unit": "g",
        })
        assert resp.status_code == 422

    async def test_zero_calories_ok(self, client: AsyncClient):
        """Zero calories valid (water, diet soda)."""
        resp = await client.post("/foods/", json={
            "name": "Diet Soda",
            "serving_size": 355, "unit": "can",
            "custom_unit": "can", "gram_weight": 355, "volume_ml": 355,
            "calories": 0, "protein": 0, "carbs": 0, "fat": 0,
        })
        assert resp.status_code == 200

    async def test_null_optional_fields_ok(self, client: AsyncClient):
        """Omitted optional fields don't break creation."""
        resp = await client.post("/foods/", json={
            "name": "Simple Food",
            "serving_size": 50, "unit": "g", "calories": 100,
        })
        assert resp.status_code == 200


class TestRegisterAndLog:
    """Test register → log → daily view flow."""

    async def test_register_custom_food(self, client: AsyncClient, db_session: AsyncSession):
        """Create + register, verify user_food."""
        resp = await client.post("/foods/", json={
            "name": "My Bar", "serving_size": 60, "unit": "bar",
            "custom_unit": "bar", "gram_weight": 60,
            "serving_description": "1 bar (60g)",
            "calories": 200, "protein": 20, "carbs": 22, "fat": 7,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        resp = await client.post("/profile/foods/register", json={
            "food_id": food_id,
            "default_quantity": 1,
            "default_unit": "1 bar (60g)",
        })
        assert resp.status_code == 201, f"Register failed: {resp.text}"
        assert resp.json()["food_id"] == food_id
        assert resp.json()["default_unit"] == "1 bar (60g)"

    async def test_quick_log_custom_food(self, client: AsyncClient, db_session: AsyncSession):
        """Create → register → log → verify in daily."""
        from datetime import date
        resp = await client.post("/foods/", json={
            "name": "Log Test Shake", "serving_size": 325, "unit": "bottle",
            "custom_unit": "bottle", "gram_weight": 325, "volume_ml": 325,
            "serving_description": "1 bottle (325g)",
            "calories": 140, "protein": 30, "carbs": 7, "fat": 1.5,
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
            "user_food_id": uf_id,
            "quantity": 1,
            "unit": "1 bottle (325g)",
        })
        assert resp.status_code in (200, 201), f"Log failed: {resp.text}"

        today = date.today().isoformat()
        resp = await client.get(f"/logs/daily/{today}")
        assert resp.status_code == 200
        meals = resp.json()["meals"]
        all_logs = [l for m in meals for l in m["logs"]]
        found = [l for l in all_logs if l["food_name"] == "Log Test Shake"]
        assert len(found) >= 1, f"Not in daily. Logs: {all_logs}"
