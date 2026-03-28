"""Tests for recipe API endpoints.

Step 3: REST API layer — schemas, routing, request/response validation.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.app import create_app
from whati8.models import Food


@pytest.fixture
async def client(db_session, seed_test_data, test_user):
    """Authenticated test client."""
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
async def sample_foods(client: AsyncClient) -> dict[str, int]:
    """Create sample custom foods via API, return {name: food_id}."""
    foods = {}
    for name, cal, protein in [("Flour", 364, 10), ("Sugar", 387, 0), ("Butter", 102, 0.1), ("Eggs", 72, 6.3)]:
        resp = await client.post("/foods/", json={
            "name": name, "serving_size": 100, "unit": "g",
            "calories": cal, "protein": protein, "carbs": 0, "fat": 0,
        })
        assert resp.status_code == 200, f"Create {name} failed: {resp.text}"
        foods[name] = resp.json()["id"]
    return foods


class TestCreateRecipeEndpoint:
    """POST /recipes/"""

    async def test_create_recipe(self, client: AsyncClient, sample_foods):
        resp = await client.post("/recipes/", json={
            "name": "Simple Cake",
            "servings": 8,
            "serving_unit": "slice",
            "ingredients": [
                {"food_id": sample_foods["Flour"], "quantity": 200, "unit": "grams", "portion_description": "grams"},
                {"food_id": sample_foods["Sugar"], "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        })
        assert resp.status_code == 200, f"Create failed: {resp.text}"
        data = resp.json()
        assert data["name"] == "Simple Cake"
        assert data["servings"] == 8
        assert data["serving_unit"] == "slice"
        assert data["current_version"] == 1
        assert data["food_id"] is not None
        assert len(data["ingredients"]) == 2

    async def test_create_returns_per_serving_nutrition(self, client: AsyncClient, sample_foods):
        resp = await client.post("/recipes/", json={
            "name": "Nutrition Check",
            "servings": 4,
            "serving_unit": "serving",
            "ingredients": [
                {"food_id": sample_foods["Flour"], "quantity": 200, "unit": "grams", "portion_description": "grams"},
            ],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "per_serving" in data
        ps = data["per_serving"]
        # 200g flour at 364 kcal/100g = 728 total, /4 servings = 182 kcal
        assert abs(ps["calories"] - 182) < 2

    async def test_create_missing_name_422(self, client: AsyncClient, sample_foods):
        resp = await client.post("/recipes/", json={
            "servings": 4, "serving_unit": "serving",
            "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        })
        assert resp.status_code == 422

    async def test_create_empty_ingredients_422(self, client: AsyncClient):
        resp = await client.post("/recipes/", json={
            "name": "Empty", "servings": 1, "serving_unit": "serving",
            "ingredients": [],
        })
        assert resp.status_code == 422 or resp.status_code == 400

    async def test_create_invalid_food_id_400(self, client: AsyncClient):
        resp = await client.post("/recipes/", json={
            "name": "Bad Food", "servings": 1, "serving_unit": "serving",
            "ingredients": [{"food_id": 999999, "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        })
        assert resp.status_code in (400, 404)


class TestGetRecipeEndpoints:
    """GET /recipes/ and GET /recipes/{id}"""

    async def test_list_recipes(self, client: AsyncClient, sample_foods):
        # Create 2 recipes
        for name in ["Recipe A", "Recipe B"]:
            await client.post("/recipes/", json={
                "name": name, "servings": 1, "serving_unit": "serving",
                "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"}],
            })
        
        resp = await client.get("/recipes/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2
        names = [r["name"] for r in data]
        assert "Recipe A" in names
        assert "Recipe B" in names

    async def test_get_recipe_by_id(self, client: AsyncClient, sample_foods):
        create_resp = await client.post("/recipes/", json={
            "name": "Get By ID", "servings": 2, "serving_unit": "portion",
            "ingredients": [
                {"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"},
                {"food_id": sample_foods["Sugar"], "quantity": 50, "unit": "grams", "portion_description": "grams"},
            ],
        })
        recipe_id = create_resp.json()["id"]
        
        resp = await client.get(f"/recipes/{recipe_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == recipe_id
        assert data["name"] == "Get By ID"
        assert len(data["ingredients"]) == 2
        assert "per_serving" in data

    async def test_get_nonexistent_recipe_404(self, client: AsyncClient):
        resp = await client.get("/recipes/999999")
        assert resp.status_code == 404


class TestUpdateRecipeEndpoint:
    """PUT /recipes/{id}"""

    async def test_update_name(self, client: AsyncClient, sample_foods):
        create_resp = await client.post("/recipes/", json={
            "name": "Old Name", "servings": 2, "serving_unit": "serving",
            "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        })
        recipe_id = create_resp.json()["id"]
        
        resp = await client.put(f"/recipes/{recipe_id}", json={"name": "New Name"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["current_version"] == 1  # no version bump

    async def test_update_servings_recalculates(self, client: AsyncClient, sample_foods):
        create_resp = await client.post("/recipes/", json={
            "name": "Recalc", "servings": 4, "serving_unit": "serving",
            "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 200, "unit": "grams", "portion_description": "grams"}],
        })
        recipe_id = create_resp.json()["id"]
        # Before: 728/4 = 182 kcal/serving
        
        resp = await client.put(f"/recipes/{recipe_id}", json={"servings": 8})
        assert resp.status_code == 200
        ps = resp.json()["per_serving"]
        # After: 728/8 = 91 kcal/serving
        assert abs(ps["calories"] - 91) < 2


class TestRecipeIngredientEndpoints:
    """POST/DELETE /recipes/{id}/ingredients"""

    async def test_add_ingredient(self, client: AsyncClient, sample_foods):
        create_resp = await client.post("/recipes/", json={
            "name": "Add Ing", "servings": 1, "serving_unit": "serving",
            "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        })
        recipe_id = create_resp.json()["id"]
        old_version = create_resp.json()["current_version"]
        
        resp = await client.post(f"/recipes/{recipe_id}/ingredients", json={
            "food_id": sample_foods["Sugar"], "quantity": 50, "unit": "grams", "portion_description": "grams",
        })
        assert resp.status_code in (200, 201), f"Add ingredient failed: {resp.text}"
        
        # Verify version incremented
        get_resp = await client.get(f"/recipes/{recipe_id}")
        assert get_resp.json()["current_version"] > old_version
        assert len(get_resp.json()["ingredients"]) == 2

    async def test_remove_ingredient(self, client: AsyncClient, sample_foods):
        create_resp = await client.post("/recipes/", json={
            "name": "Remove Ing", "servings": 1, "serving_unit": "serving",
            "ingredients": [
                {"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"},
                {"food_id": sample_foods["Sugar"], "quantity": 50, "unit": "grams", "portion_description": "grams"},
            ],
        })
        recipe_id = create_resp.json()["id"]
        ing_id = create_resp.json()["ingredients"][0]["id"]
        
        resp = await client.delete(f"/recipes/{recipe_id}/ingredients/{ing_id}")
        assert resp.status_code in (200, 204), f"Remove failed: {resp.text}"
        
        get_resp = await client.get(f"/recipes/{recipe_id}")
        assert len(get_resp.json()["ingredients"]) == 1

    async def test_circular_dependency_rejected(self, client: AsyncClient, sample_foods):
        """Adding a recipe's own food should be rejected via API."""
        create_resp = await client.post("/recipes/", json={
            "name": "Self Ref", "servings": 1, "serving_unit": "serving",
            "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        })
        recipe_id = create_resp.json()["id"]
        food_id = create_resp.json()["food_id"]
        
        resp = await client.post(f"/recipes/{recipe_id}/ingredients", json={
            "food_id": food_id, "quantity": 1, "unit": "serving", "portion_description": "serving",
        })
        assert resp.status_code == 400
        assert "circular" in resp.json().get("detail", "").lower() or "circular" in str(resp.json()).lower()


class TestDependencyCheckEndpoint:
    """GET /recipes/{id}/can-add/{food_id}"""

    async def test_can_add_plain_food(self, client: AsyncClient, sample_foods):
        create_resp = await client.post("/recipes/", json={
            "name": "Dep Check", "servings": 1, "serving_unit": "serving",
            "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        })
        recipe_id = create_resp.json()["id"]
        
        resp = await client.get(f"/recipes/{recipe_id}/can-add/{sample_foods['Sugar']}")
        assert resp.status_code == 200
        assert resp.json()["allowed"] is True

    async def test_cannot_add_self(self, client: AsyncClient, sample_foods):
        create_resp = await client.post("/recipes/", json={
            "name": "Self Check", "servings": 1, "serving_unit": "serving",
            "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        })
        recipe_id = create_resp.json()["id"]
        food_id = create_resp.json()["food_id"]
        
        resp = await client.get(f"/recipes/{recipe_id}/can-add/{food_id}")
        assert resp.status_code == 200
        assert resp.json()["allowed"] is False


class TestDeleteRecipeEndpoint:
    """DELETE /recipes/{id}"""

    async def test_delete_recipe(self, client: AsyncClient, sample_foods):
        create_resp = await client.post("/recipes/", json={
            "name": "To Delete", "servings": 1, "serving_unit": "serving",
            "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        })
        recipe_id = create_resp.json()["id"]
        
        resp = await client.delete(f"/recipes/{recipe_id}")
        assert resp.status_code in (200, 204)
        
        # Should be gone
        get_resp = await client.get(f"/recipes/{recipe_id}")
        assert get_resp.status_code == 404

    async def test_delete_marks_food_expired(self, client: AsyncClient, sample_foods, db_session: AsyncSession):
        create_resp = await client.post("/recipes/", json={
            "name": "Expire On Delete", "servings": 1, "serving_unit": "serving",
            "ingredients": [{"food_id": sample_foods["Flour"], "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        })
        food_id = create_resp.json()["food_id"]
        recipe_id = create_resp.json()["id"]
        
        await client.delete(f"/recipes/{recipe_id}")
        
        food = await db_session.get(Food, food_id)
        assert food is not None, "Food should still exist for historical logs"
        assert food.is_recipe_expired is True
