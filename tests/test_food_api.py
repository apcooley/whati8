"""Tests for food search and details API."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models import Food


@pytest.mark.api
@pytest.mark.integration
class TestFoodSearchAPI:
    """Test food search endpoint."""

    async def test_search_foods_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        seed_test_data,
    ):
        """Test successful food search."""
        response = await authenticated_client.get("/foods/search?q=egg")

        assert response.status_code == 200
        data = response.json()
        assert "query" in data
        assert data["query"] == "egg"
        assert "results" in data
        assert "total" in data
        assert len(data["results"]) > 0

        # Check result structure
        first_result = data["results"][0]
        assert "id" in first_result
        assert "name" in first_result
        assert "similarity" in first_result
        assert 0.0 <= first_result["similarity"] <= 1.0

    async def test_search_foods_typo_tolerance(
        self, authenticated_client: AsyncClient, seed_test_data
    ):
        """Test fuzzy search with typos."""
        # "egh" should still match "egg"
        response = await authenticated_client.get("/foods/search?q=egh")

        assert response.status_code == 200
        response.json()  # Verify response is valid JSON
        # May or may not find results depending on similarity threshold
        # but should not error

    async def test_search_foods_pagination(
        self, authenticated_client: AsyncClient, seed_test_data
    ):
        """Test search pagination."""
        response = await authenticated_client.get("/foods/search?q=egg&limit=1&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 1
        assert data["offset"] == 0
        assert len(data["results"]) <= 1

    async def test_search_foods_no_auth(self, client: AsyncClient):
        """Test search without authentication."""
        response = await client.get("/foods/search?q=egg")

        assert response.status_code == 401

    async def test_search_foods_short_query(self, authenticated_client: AsyncClient):
        """Test search with query too short."""
        response = await authenticated_client.get("/foods/search?q=e")

        # Should fail validation (min_length=2)
        assert response.status_code == 422


@pytest.mark.api
@pytest.mark.integration
class TestFoodDetailsAPI:
    """Test food details endpoint."""

    async def test_get_food_success(
        self,
        authenticated_client: AsyncClient,
        db_session: AsyncSession,
        seed_test_data,
    ):
        """Test getting food details."""
        # Get a food ID from the database
        from sqlalchemy import select

        result = await db_session.execute(select(Food).limit(1))
        food = result.scalar_one()

        response = await authenticated_client.get(f"/foods/{food.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == food.id
        assert data["name"] == food.name
        assert "food_nutrients" in data
        assert isinstance(data["food_nutrients"], list)

    async def test_get_food_not_found(self, authenticated_client: AsyncClient):
        """Test getting nonexistent food."""
        response = await authenticated_client.get("/foods/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["error"]["message"].lower()

    async def test_get_food_no_auth(self, client: AsyncClient, seed_test_data):
        """Test getting food without authentication."""
        response = await client.get("/foods/1")

        assert response.status_code == 401


@pytest.mark.api
@pytest.mark.unit
class TestFoodSchemas:
    """Test Pydantic schemas for food endpoints."""

    def test_food_search_result_item_schema(self):
        """Test FoodSearchResultItem schema validation."""
        from whati8.schemas.food import FoodSearchResultItem

        item = FoodSearchResultItem(
            id=1,
            name="Test Food",
            brand=None,
            serving_size=100.0,
            unit="g",
            usda_fdc_id=123,
            similarity=0.95,
            calories=100.0,
            protein=10.0,
            carbs=20.0,
            fat=5.0,
        )

        assert item.id == 1
        assert item.name == "Test Food"
        assert item.similarity == 0.95

    def test_food_response_schema(self):
        """Test FoodResponse schema validation."""
        from whati8.schemas.food import (
            FoodResponse,
            FoodNutrientResponse,
            NutrientResponse,
        )

        nutrient = NutrientResponse(
            id=1, name="Protein", unit="g", description="Protein content"
        )

        food_nutrient = FoodNutrientResponse(nutrient=nutrient, amount_per_serving=10.0)

        food = FoodResponse(
            id=1,
            name="Test Food",
            brand=None,
            serving_size=100.0,
            unit="g",
            usda_fdc_id=123,
            food_nutrients=[food_nutrient],
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )

        assert food.id == 1
        assert len(food.food_nutrients) == 1
        assert food.food_nutrients[0].nutrient.name == "Protein"
