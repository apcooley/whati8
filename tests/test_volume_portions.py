"""Tests for volume-based portion creation on custom foods.

Volume applies to ANY food (yogurt, peanut butter, honey, etc.), not just beverages.
When volume_ml is provided, the backend should create portions for ALL common
volume units (cup, tbsp, tsp, fl oz, mL) using density-based gram weights.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.app import create_app
from whati8.models import Food, FoodPortion


# Volume unit → mL conversion factors
VOLUME_TO_ML = {
    'tsp': 4.929,
    'tbsp': 14.787,
    'fl oz': 29.5735,
    'cup': 236.588,
    'mL': 1.0,
}


@pytest.fixture
async def client(db_session, seed_test_data, test_user):
    app = create_app()
    from whati8.api.deps import get_db
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/auth/login", json={
            "login": "testuser", "password": "testpassword123",
        })
        assert resp.status_code == 200
        ac.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield ac


class TestVolumePortionCreation:
    """When volume_ml is provided, create volume-based portions."""

    async def test_yogurt_creates_volume_portions(self, client, db_session: AsyncSession):
        """170g yogurt with volume_ml=177.4 (3/4 cup) → creates cup, tbsp, tsp, fl oz, mL portions."""
        resp = await client.post("/foods/", json={
            "name": "Greek Yogurt",
            "serving_size": 170,
            "unit": "g",
            "volume_ml": 177.4,  # 3/4 cup in mL
            "calories": 90,
            "protein": 18,
            "carbs": 6,
            "fat": 0,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        portions = {p.unit_name: p for p in result.scalars().all()}

        # Density = 170 / 177.4 = 0.958 g/mL
        density = 170 / 177.4

        # Should have volume portions
        assert "cup" in portions, f"Missing cup. Got: {list(portions.keys())}"
        assert "tbsp" in portions, f"Missing tbsp. Got: {list(portions.keys())}"
        assert "tsp" in portions, f"Missing tsp. Got: {list(portions.keys())}"
        assert "fl oz" in portions, f"Missing fl oz. Got: {list(portions.keys())}"
        assert "mL" in portions, f"Missing mL. Got: {list(portions.keys())}"

        # Verify gram weights based on density
        assert abs(float(portions["cup"].gram_weight) - density * 236.588) < 1
        assert abs(float(portions["tbsp"].gram_weight) - density * 14.787) < 0.5
        assert abs(float(portions["tsp"].gram_weight) - density * 4.929) < 0.2
        assert abs(float(portions["fl oz"].gram_weight) - density * 29.5735) < 0.5

    async def test_honey_density(self, client, db_session: AsyncSession):
        """Heavy liquid: 21g honey in 1 tbsp (14.787 mL) → density 1.42."""
        resp = await client.post("/foods/", json={
            "name": "Honey",
            "serving_size": 21,
            "unit": "g",
            "volume_ml": 14.787,  # 1 tbsp
            "calories": 64,
            "protein": 0,
            "carbs": 17,
            "fat": 0,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        portions = {p.unit_name: p for p in result.scalars().all()}

        density = 21 / 14.787  # ~1.42

        assert "tbsp" in portions
        assert abs(float(portions["tbsp"].gram_weight) - density * 14.787) < 0.5
        assert "cup" in portions
        assert abs(float(portions["cup"].gram_weight) - density * 236.588) < 2

    async def test_no_volume_no_volume_portions(self, client, db_session: AsyncSession):
        """Without volume_ml, no volume portions should be created."""
        resp = await client.post("/foods/", json={
            "name": "Dry Oats",
            "serving_size": 40,
            "unit": "g",
            "calories": 150,
            "protein": 5,
            "carbs": 27,
            "fat": 2.5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        portions = {p.unit_name: p for p in result.scalars().all()}

        assert "cup" not in portions
        assert "tbsp" not in portions
        assert "tsp" not in portions
        assert "fl oz" not in portions
        assert "mL" not in portions
        # Should still have grams and oz
        assert "g" in portions
        assert "oz" in portions

    async def test_custom_unit_with_volume(self, client, db_session: AsyncSession):
        """Custom unit + volume: 1 container (170g, 177.4mL) → custom + volume + weight portions."""
        resp = await client.post("/foods/", json={
            "name": "Yogurt Cup",
            "serving_size": 170,
            "unit": "container",
            "custom_unit": "container",
            "gram_weight": 170,
            "volume_ml": 177.4,
            "calories": 90,
            "protein": 18,
            "carbs": 6,
            "fat": 0,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        portions = {p.unit_name: p for p in result.scalars().all()}

        # Should have custom unit
        assert "container" in portions
        # Should have volume units
        assert "cup" in portions
        assert "tbsp" in portions
        # Should have weight units
        assert "g" in portions
        assert "oz" in portions

    async def test_volume_portions_no_duplicates(self, client, db_session: AsyncSession):
        """If custom_unit is 'cup', don't create duplicate cup portion."""
        resp = await client.post("/foods/", json={
            "name": "Flour by Cup",
            "serving_size": 125,
            "unit": "cup",
            "custom_unit": "cup",
            "gram_weight": 125,
            "volume_ml": 236.588,  # 1 cup
            "calories": 455,
            "protein": 13,
            "carbs": 95,
            "fat": 1,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]

        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food_id)
        )
        portions = result.scalars().all()
        cup_count = sum(1 for p in portions if p.unit_name == "cup")
        assert cup_count == 1, f"Should have exactly 1 cup portion, got {cup_count}"
