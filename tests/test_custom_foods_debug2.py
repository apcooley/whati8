"""Debug test for list user foods."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_list_user_foods_debug(
    authenticated_client: AsyncClient, db_session: AsyncSession, seed_test_data
):
    """Debug test for listing user foods."""
    # Create a food
    create_response = await authenticated_client.post(
        "/foods/",
        json={
            "name": "Test Food",
            "serving_size": 100,
            "calories": 100,
        },
    )

    print(f"Create response status: {create_response.status_code}")
    print(f"Create response body: {create_response.text}")

    # Get user foods
    response = await authenticated_client.get("/foods/mine")

    print(f"List response status: {response.status_code}")
    print(f"List response body: {response.text}")

    assert response.status_code == 200, f"Got status {response.status_code}: {response.text}"
