"""Tests for batch food logging endpoint."""

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models import Food, FoodLog, Meal, User


async def get_test_food_and_meals(db_session: AsyncSession):
    """Helper to get test food and meal IDs."""
    food_result = await db_session.execute(select(Food).limit(1))
    food = food_result.scalar_one()
    
    meals_result = await db_session.execute(select(Meal).order_by(Meal.id).limit(4))
    meals = meals_result.scalars().all()
    
    return food, meals


@pytest.mark.api
@pytest.mark.db
class TestBatchLogEndpoint:
    """Test POST /logs/batch endpoint."""

    async def test_batch_log_success(
        self, authenticated_client: AsyncClient, seed_test_data, db_session: AsyncSession
    ):
        """Test successfully logging multiple foods in one batch."""
        food, meals = await get_test_food_and_meals(db_session)
        meal_id = meals[0].id

        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [
                    {"food_id": food.id, "quantity": 2.0, "meal_id": meal_id},
                    {"food_id": food.id, "quantity": 1.5, "meal_id": meal_id},
                ],
                "logged_at": datetime.utcnow().isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["logged"] == 2
        assert "Successfully logged 2 food" in data["message"]

    async def test_batch_log_empty_list_rejected(self, authenticated_client: AsyncClient):
        """Test batch with empty entries list returns validation error."""
        response = await authenticated_client.post(
            "/logs/batch",
            json={"entries": []},
        )

        # Schema has min_length=1 on entries
        assert response.status_code == 422

    async def test_batch_log_invalid_food_id_fails(
        self, authenticated_client: AsyncClient, seed_test_data, db_session: AsyncSession
    ):
        """Test that invalid food_id causes batch to fail."""
        food, meals = await get_test_food_and_meals(db_session)
        meal_id = meals[0].id

        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [
                    {"food_id": food.id, "quantity": 2.0, "meal_id": meal_id},  # Valid
                    {"food_id": 99999, "quantity": 1.0, "meal_id": meal_id},  # Invalid
                ],
                "logged_at": datetime.utcnow().isoformat(),
            },
        )

        # Should fail with 404 for missing food
        assert response.status_code == 404

    async def test_batch_log_no_auth(self, client: AsyncClient):
        """Test batch endpoint requires authentication."""
        response = await client.post(
            "/logs/batch",
            json={
                "entries": [{"food_id": 1, "quantity": 1.0, "meal_id": 1}],
            },
        )

        assert response.status_code == 401

    async def test_batch_log_default_timestamp(
        self, authenticated_client: AsyncClient, seed_test_data, db_session: AsyncSession
    ):
        """Test that logged_at defaults to now if not provided."""
        food, meals = await get_test_food_and_meals(db_session)
        meal_id = meals[0].id

        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [{"food_id": food.id, "quantity": 1.0, "meal_id": meal_id}],
                # No logged_at - should default to now
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["logged"] == 1


@pytest.mark.api
@pytest.mark.db
class TestBatchLogValidation:
    """Validation tests for batch logging."""

    async def test_batch_log_zero_quantity_rejected(
        self, authenticated_client: AsyncClient, seed_test_data, db_session: AsyncSession
    ):
        """Test that zero quantity is rejected (gt=0 validation)."""
        food, meals = await get_test_food_and_meals(db_session)

        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [{"food_id": food.id, "quantity": 0, "meal_id": meals[0].id}],
            },
        )

        assert response.status_code == 422

    async def test_batch_log_negative_quantity_rejected(
        self, authenticated_client: AsyncClient, seed_test_data, db_session: AsyncSession
    ):
        """Test that negative quantity is rejected."""
        food, meals = await get_test_food_and_meals(db_session)

        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [{"food_id": food.id, "quantity": -1.0, "meal_id": meals[0].id}],
            },
        )

        assert response.status_code == 422

    async def test_batch_log_missing_food_id(self, authenticated_client: AsyncClient):
        """Test that missing food_id returns validation error."""
        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [{"quantity": 1.0, "meal_id": 1}],
            },
        )
        assert response.status_code == 422

    async def test_batch_log_missing_quantity(self, authenticated_client: AsyncClient):
        """Test that missing quantity returns validation error."""
        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [{"food_id": 1, "meal_id": 1}],
            },
        )
        assert response.status_code == 422

    async def test_batch_log_missing_meal_id(self, authenticated_client: AsyncClient):
        """Test that missing meal_id returns validation error."""
        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [{"food_id": 1, "quantity": 1.0}],
            },
        )
        assert response.status_code == 422


@pytest.mark.api
@pytest.mark.db
class TestBatchLogEdgeCases:
    """Edge case tests for batch logging."""

    async def test_batch_log_same_food_twice(
        self, authenticated_client: AsyncClient, seed_test_data, db_session: AsyncSession
    ):
        """Test logging same food twice in one batch creates separate entries."""
        food, meals = await get_test_food_and_meals(db_session)
        meal_id = meals[0].id

        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [
                    {"food_id": food.id, "quantity": 2.0, "meal_id": meal_id},
                    {"food_id": food.id, "quantity": 1.0, "meal_id": meal_id},  # Same food
                ],
                "logged_at": datetime.utcnow().isoformat(),
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["logged"] == 2

    async def test_batch_log_single_entry(
        self, authenticated_client: AsyncClient, seed_test_data, db_session: AsyncSession
    ):
        """Test batch with single entry works."""
        food, meals = await get_test_food_and_meals(db_session)
        meal_id = meals[1].id if len(meals) > 1 else meals[0].id

        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [{"food_id": food.id, "quantity": 1.5, "meal_id": meal_id}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["logged"] == 1

    async def test_batch_log_different_meals(
        self, authenticated_client: AsyncClient, seed_test_data, db_session: AsyncSession
    ):
        """Test batch can contain entries for different meals."""
        food, meals = await get_test_food_and_meals(db_session)
        
        # Use up to 3 different meal IDs
        meal_ids = [m.id for m in meals[:3]]

        entries = [
            {"food_id": food.id, "quantity": 1.0 + i, "meal_id": mid}
            for i, mid in enumerate(meal_ids)
        ]

        response = await authenticated_client.post(
            "/logs/batch",
            json={"entries": entries},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["logged"] == len(meal_ids)

    async def test_batch_log_invalid_meal_id_fails(
        self, authenticated_client: AsyncClient, seed_test_data, db_session: AsyncSession
    ):
        """Test that invalid meal_id causes batch to fail (FK constraint)."""
        food, meals = await get_test_food_and_meals(db_session)

        response = await authenticated_client.post(
            "/logs/batch",
            json={
                "entries": [
                    {"food_id": food.id, "quantity": 1.0, "meal_id": 99999},  # Invalid meal
                ],
            },
        )

        # Should fail (FK constraint violation)
        assert response.status_code == 500  # Or could be 400 with better error handling
