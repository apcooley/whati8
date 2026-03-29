"""Tests for recipe ingredient food search.

The recipe ingredient search should:
1. Search user's registered foods (user_foods) FIRST
2. Include user-created custom foods
3. Fall back to USDA for unregistered foods
4. NOT show expired recipe versions
5. Support partial name matching
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.app import create_app


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
async def registered_foods(client: AsyncClient) -> dict[str, int]:
    """Create and register several custom foods."""
    foods = {}
    items = [
        ("Fage Greek Yogurt", 170, 90),
        ("Chobani Vanilla Yogurt", 150, 120),
        ("Steel Cut Oats", 40, 150),
        ("Peanut Butter", 32, 190),
    ]
    for name, serving, cal in items:
        resp = await client.post("/foods/", json={
            "name": name, "serving_size": serving, "unit": "g",
            "calories": cal, "protein": 10, "carbs": 15, "fat": 5,
        })
        assert resp.status_code == 200
        food_id = resp.json()["id"]
        
        resp = await client.post("/profile/foods/register", json={
            "food_id": food_id, "default_quantity": 1, "default_unit": "grams",
        })
        assert resp.status_code == 201
        foods[name] = food_id
    
    return foods


class TestProfileFoodSearch:
    """GET /profile/foods/search?q=... — search registered foods."""

    async def test_search_endpoint_exists(self, client: AsyncClient, registered_foods):
        """Search endpoint should exist and return results."""
        resp = await client.get("/profile/foods/search?q=yogurt")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_search_finds_registered_food(self, client: AsyncClient, registered_foods):
        """Searching 'yogurt' should find registered yogurt foods."""
        resp = await client.get("/profile/foods/search?q=yogurt")
        assert resp.status_code == 200
        data = resp.json()
        names = [item["food"]["name"] if "food" in item else item.get("name", "") for item in data]
        assert any("yogurt" in n.lower() for n in names), f"No yogurt in results: {names}"

    async def test_search_finds_partial_match(self, client: AsyncClient, registered_foods):
        """Searching 'fage' should find 'Fage Greek Yogurt'."""
        resp = await client.get("/profile/foods/search?q=fage")
        assert resp.status_code == 200
        data = resp.json()
        names = [item["food"]["name"] if "food" in item else item.get("name", "") for item in data]
        assert any("fage" in n.lower() for n in names), f"No fage in results: {names}"

    async def test_search_returns_food_id(self, client: AsyncClient, registered_foods):
        """Each result should have a food_id."""
        resp = await client.get("/profile/foods/search?q=oats")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        item = data[0]
        # Should have food_id either directly or via nested food object
        food_id = item.get("food_id") or item.get("food", {}).get("id")
        assert food_id is not None

    async def test_search_empty_query_returns_all(self, client: AsyncClient, registered_foods):
        """Empty query should return recent/all registered foods."""
        resp = await client.get("/profile/foods/search?q=")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 4  # We registered 4 foods

    async def test_search_no_match_returns_empty(self, client: AsyncClient, registered_foods):
        """Searching for something not registered returns empty."""
        resp = await client.get("/profile/foods/search?q=xyznonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0

    async def test_expired_foods_excluded(self, client: AsyncClient, registered_foods, db_session: AsyncSession):
        """Expired recipe foods should not appear in search."""
        from whati8.models import Food
        
        # Create a recipe, which creates a food
        resp = await client.post("/recipes/", json={
            "name": "Yogurt Bowl Recipe",
            "servings": 1, "serving_unit": "serving",
            "ingredients": [{"food_id": registered_foods["Fage Greek Yogurt"], 
                           "quantity": 170, "unit": "grams", "portion_description": "grams"}],
        })
        assert resp.status_code == 200
        recipe_food_id = resp.json()["food_id"]
        
        # Expire the food
        food = await db_session.get(Food, recipe_food_id)
        food.is_recipe_expired = True
        await db_session.commit()
        
        # Search should not return the expired food
        resp = await client.get("/profile/foods/search?q=yogurt bowl")
        data = resp.json()
        food_ids = [item.get("food_id") or item.get("food", {}).get("id") for item in data]
        assert recipe_food_id not in food_ids
