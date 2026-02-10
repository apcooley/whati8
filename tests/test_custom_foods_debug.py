"""Debug test for custom foods."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models import User


@pytest.mark.asyncio
async def test_create_custom_food_debug(
    authenticated_client: AsyncClient, db_session: AsyncSession, seed_test_data
):
    """Debug test for creating a custom food."""
    response = await authenticated_client.post(
        "/foods/",
        json={
            "name": "Vanilla Yogurt",
            "brand": "Acme Brand",
            "serving_size": 150,
            "unit": "g",
            "calories": 95,
            "protein": 5,
            "carbs": 12,
            "fat": 0.5,
            "fiber": 0,
            "notes": "Plain vanilla yogurt",
        },
    )

    print(f"Status: {response.status_code}")
    print(f"Body: {response.text}")
    print(f"Headers: {response.headers}")

    assert response.status_code == 200, f"Got status {response.status_code}: {response.text}"
