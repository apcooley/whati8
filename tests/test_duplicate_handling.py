"""Tests for duplicate and conflict handling.

Covers:
1. Registering same food twice → should 409 with clear message
2. Quick-logging same food multiple times → should succeed (no unique constraint)
3. Creating foods with same name → should succeed (different IDs)
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.app import create_app


@pytest.fixture
async def client(db_session, seed_test_data, test_user):
    """Authenticated test client."""
    app = create_app()
    from whati8.api.deps import get_db
    app.dependency_overrides[get_db] = lambda: db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/auth/login", json={
            "login": "testuser",
            "password": "testpassword123",
        })
        assert resp.status_code == 200
        ac.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        yield ac


async def create_and_register(client, name="Test Food", cal=100):
    """Helper: create custom food + register."""
    resp = await client.post("/foods/", json={
        "name": name, "serving_size": 100, "unit": "g",
        "calories": cal, "protein": 5, "carbs": 10, "fat": 3,
    })
    assert resp.status_code == 200
    food_id = resp.json()["id"]
    
    resp = await client.post("/profile/foods/register", json={
        "food_id": food_id, "default_quantity": 1, "default_unit": "grams",
    })
    assert resp.status_code == 201
    return food_id, resp.json()["id"]


class TestDuplicateRegistration:
    async def test_register_same_food_twice_returns_409(self, client: AsyncClient):
        """Registering the same food_id twice should return 409."""
        food_id, _ = await create_and_register(client, "Dup Food")
        
        resp = await client.post("/profile/foods/register", json={
            "food_id": food_id, "default_quantity": 1, "default_unit": "grams",
        })
        assert resp.status_code in (400, 409), f"Expected 400/409, got {resp.status_code}: {resp.text}"

    async def test_409_error_message_is_clear(self, client: AsyncClient):
        """409 should have a human-readable error message."""
        food_id, _ = await create_and_register(client, "Msg Food")
        
        resp = await client.post("/profile/foods/register", json={
            "food_id": food_id, "default_quantity": 1, "default_unit": "grams",
        })
        assert resp.status_code in (400, 409)
        body = resp.json()
        msg = body.get("error", {}).get("message", "") or body.get("detail", "")
        assert msg, f"No error message in response: {body}"
        assert "already" in msg.lower(), f"Message should mention 'already': {msg}"


class TestMultipleQuickLogs:
    async def test_log_same_food_twice_succeeds(self, client: AsyncClient):
        """Quick-logging the same food multiple times should always succeed."""
        _, uf_id = await create_and_register(client, "Multi Log Food")
        
        for i in range(3):
            resp = await client.post("/logs/quick", json={
                "user_food_id": uf_id, "quantity": 1, "unit": "grams",
            })
            assert resp.status_code in (200, 201), (
                f"Log #{i+1} failed: {resp.status_code} {resp.text}"
            )


class TestSameNameFoods:
    async def test_create_foods_with_same_name(self, client: AsyncClient):
        """Creating two foods with the same name but different IDs should work."""
        ids = []
        for _ in range(2):
            resp = await client.post("/foods/", json={
                "name": "Same Name Food", "serving_size": 100, "unit": "g",
                "calories": 100, "protein": 5, "carbs": 10, "fat": 3,
            })
            assert resp.status_code == 200
            ids.append(resp.json()["id"])
        
        assert ids[0] != ids[1], "Should create distinct food entries"

    async def test_register_different_foods_with_same_name(self, client: AsyncClient):
        """Registering two different food_ids (same name) should both succeed."""
        ids = []
        for i in range(2):
            resp = await client.post("/foods/", json={
                "name": "Same Name Reg", "serving_size": 100, "unit": "g",
                "calories": 100 + i, "protein": 5, "carbs": 10, "fat": 3,
            })
            assert resp.status_code == 200
            food_id = resp.json()["id"]
            ids.append(food_id)
            
            resp = await client.post("/profile/foods/register", json={
                "food_id": food_id, "default_quantity": 1, "default_unit": "grams",
            })
            assert resp.status_code == 201, (
                f"Register food #{i+1} (id={food_id}) failed: {resp.status_code} {resp.text}"
            )
