"""Tests for recipe ingredient portion matching / gram conversion.

The _get_quantity_in_grams function must correctly resolve ingredient units
to gram weights by matching against the food's portions.

Key issue: USDA portions have descriptions like "1.0 undetermined serving (43.0g)"
but the frontend sends the CLEANED version: "serving (43.0g)" or "serving (43g)".
The matching must handle this normalization.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.app import create_app
from whati8.models import Food
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
async def usda_food_with_portions(db_session: AsyncSession, seed_test_data) -> Food:
    """Create a USDA-like food (no created_by_user_id) with realistic portions."""
    from whati8.models import FoodPortion
    
    food = Food(name="Hamburger Bun", serving_size=43, unit="g", created_by_user_id=None)
    db_session.add(food)
    await db_session.flush()
    
    energy = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Energy"))
    protein = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Protein"))
    if energy:
        db_session.add(FoodNutrient(food_id=food.id, nutrient_id=energy.id, amount_per_serving=273))
    if protein:
        db_session.add(FoodNutrient(food_id=food.id, nutrient_id=protein.id, amount_per_serving=8.07))
    
    # USDA-style portion with "1.0 undetermined" prefix
    db_session.add(FoodPortion(
        food_id=food.id, amount=1, unit_name="undetermined",
        gram_weight=43, portion_description="1.0 undetermined serving (43.0g)",
        sequence_number=1,
    ))
    await db_session.commit()
    return food


@pytest.fixture
async def custom_food(db_session: AsyncSession, seed_test_data, test_user) -> Food:
    """Create a custom food with clean portions."""
    from whati8.models import FoodPortion
    
    food = Food(name="Custom Pork", serving_size=100, unit="g", created_by_user_id=test_user.id)
    db_session.add(food)
    await db_session.flush()
    
    energy = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Energy"))
    protein = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Protein"))
    if energy:
        db_session.add(FoodNutrient(food_id=food.id, nutrient_id=energy.id, amount_per_serving=200))
    if protein:
        db_session.add(FoodNutrient(food_id=food.id, nutrient_id=protein.id, amount_per_serving=25))
    
    db_session.add(FoodPortion(
        food_id=food.id, amount=1, unit_name="g",
        gram_weight=1, portion_description="grams", sequence_number=1,
    ))
    db_session.add(FoodPortion(
        food_id=food.id, amount=1, unit_name="oz",
        gram_weight=28.35, portion_description="oz", sequence_number=2,
    ))
    await db_session.commit()
    return food


class TestRecipePortionMatching:
    """Verify ingredient gram conversion matches correctly."""

    async def test_usda_cleaned_portion_description(
        self, client, db_session, usda_food_with_portions, custom_food
    ):
        """'serving (43.0g)' should match USDA's '1.0 undetermined serving (43.0g)'."""
        resp = await client.post("/recipes/", json={
            "name": "Bun Test",
            "servings": 1,
            "serving_unit": "sandwich",
            "ingredients": [
                {
                    "food_id": usda_food_with_portions.id,
                    "quantity": 1,
                    "unit": "serving (43.0g)",
                    "portion_description": "serving (43.0g)",
                },
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        # 1 bun = 43g. USDA 273 kcal/100g → 43g = 117.39 kcal
        # Energy is in kcal in test DB
        cal = data["per_serving"]["calories"]
        assert abs(cal - 117.4) < 5, f"Expected ~117 kcal for 1 bun (43g), got {cal}"

    async def test_usda_cleaned_portion_without_decimal(
        self, client, db_session, usda_food_with_portions, custom_food
    ):
        """'serving (43g)' (no .0) should also match."""
        resp = await client.post("/recipes/", json={
            "name": "Bun Test 2",
            "servings": 1,
            "serving_unit": "sandwich",
            "ingredients": [
                {
                    "food_id": usda_food_with_portions.id,
                    "quantity": 1,
                    "unit": "serving (43g)",
                    "portion_description": "serving (43g)",
                },
            ],
        })
        assert resp.status_code == 200
        cal = resp.json()["per_serving"]["calories"]
        assert abs(cal - 117.4) < 5, f"Expected ~117 kcal, got {cal}"

    async def test_grams_unit_works(self, client, custom_food):
        """Unit 'grams' should use quantity directly as grams."""
        resp = await client.post("/recipes/", json={
            "name": "Grams Test",
            "servings": 1,
            "serving_unit": "serving",
            "ingredients": [
                {
                    "food_id": custom_food.id,
                    "quantity": 50,
                    "unit": "grams",
                    "portion_description": "grams",
                },
            ],
        })
        assert resp.status_code == 200
        cal = resp.json()["per_serving"]["calories"]
        # Custom: 200 kcal per 100g. 50g = 100 kcal.
        assert abs(cal - 100) < 5, f"Expected 100 kcal for 50g, got {cal}"

    async def test_combined_recipe_nutrition_adds_up(
        self, client, usda_food_with_portions, custom_food
    ):
        """Recipe with USDA bun + custom pork: totals should be sum of parts."""
        resp = await client.post("/recipes/", json={
            "name": "Combo Test",
            "servings": 1,
            "serving_unit": "sandwich",
            "ingredients": [
                {"food_id": custom_food.id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
                {"food_id": usda_food_with_portions.id, "quantity": 1, "unit": "serving (43.0g)", "portion_description": "serving (43.0g)"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        
        cal = data["per_serving"]["calories"]
        protein = data["per_serving"]["protein_g"]
        weight = data["per_serving"]["weight_g"]
        
        # Pork: 200 kcal per 100g → 200 kcal for 100g
        # Bun: 273 kcal per 100g → 117.4 kcal for 43g
        # Total: 317.4 kcal
        assert abs(cal - 317.4) < 5, f"Expected ~317 kcal, got {cal}"
        
        # Pork: 25g protein per 100g → 25g for 100g
        # Bun: 8.07g per 100g → 3.47g for 43g
        # Total: 28.47g
        assert abs(protein - 28.5) < 2, f"Expected ~28.5g protein, got {protein}"
        
        # Total weight: 100 + 43 = 143g
        assert abs(weight - 143) < 1, f"Expected 143g total weight, got {weight}"

    async def test_multiple_of_same_portion(self, client, usda_food_with_portions):
        """2 buns = 86g → double the nutrition."""
        resp = await client.post("/recipes/", json={
            "name": "Double Bun",
            "servings": 1,
            "serving_unit": "serving",
            "ingredients": [
                {"food_id": usda_food_with_portions.id, "quantity": 2, "unit": "serving (43.0g)", "portion_description": "serving (43.0g)"},
            ],
        })
        assert resp.status_code == 200
        cal = resp.json()["per_serving"]["calories"]
        # 2 buns × 43g each = 86g → 273 * 86/100 = 234.8 kcal
        assert abs(cal - 234.8) < 5, f"Expected ~235 kcal for 2 buns, got {cal}"

    async def test_oz_portion_works(self, client, custom_food):
        """2 oz of custom food → correct grams."""
        resp = await client.post("/recipes/", json={
            "name": "Oz Test",
            "servings": 1,
            "serving_unit": "serving",
            "ingredients": [
                {"food_id": custom_food.id, "quantity": 2, "unit": "oz", "portion_description": "oz"},
            ],
        })
        assert resp.status_code == 200
        cal = resp.json()["per_serving"]["calories"]
        # 2 oz = 56.7g. Custom: 200 kcal per 100g → 113.4 kcal
        assert abs(cal - 113.4) < 5, f"Expected ~113 kcal for 2oz, got {cal}"
