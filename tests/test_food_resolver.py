"""Tests for AI-powered food resolution."""

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.schemas.food_resolver import (
    FoodResolveRequest,
    ParsedFoodItem,
)
from whati8.services.food_resolver import FoodResolverService


@pytest.mark.ai
@pytest.mark.unit
class TestFoodResolverService:
    """Test food resolver service layer."""

    @patch("whati8.services.food_resolver.Anthropic")
    async def test_parse_food_text_success(self, mock_anthropic_class):
        """Test parsing natural language with mocked Claude API."""
        # Mock Claude API response
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "extract_food_items"
        mock_tool_use.input = {
            "items": [
                {
                    "food_name": "egg",
                    "quantity": 2.0,
                    "unit": "pieces",
                    "original_text": "2 eggs",
                    "confidence": 0.95,
                },
                {
                    "food_name": "toast",
                    "quantity": 2.0,
                    "unit": "slices",
                    "original_text": "toast",
                    "confidence": 0.85,
                },
            ],
            "meal_detected": "breakfast",
        }
        mock_response.content = [mock_tool_use]
        mock_client.messages.create.return_value = mock_response

        # Call service
        parsed_items, meal_name = await FoodResolverService.parse_food_text(
            "I had 2 eggs and toast for breakfast"
        )

        assert len(parsed_items) == 2
        assert parsed_items[0].food_name == "egg"
        assert parsed_items[0].quantity == 2.0
        assert parsed_items[1].food_name == "toast"
        assert meal_name == "breakfast"

    @patch("whati8.services.food_resolver.Anthropic")
    async def test_parse_food_text_no_items(self, mock_anthropic_class):
        """Test parsing with no extractable items."""
        # Mock Claude API response with no items
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "extract_food_items"
        mock_tool_use.input = {"items": [], "meal_detected": "unknown"}
        mock_response.content = [mock_tool_use]
        mock_client.messages.create.return_value = mock_response

        # Should raise ValueError
        with pytest.raises(ValueError, match="No food items could be extracted"):
            await FoodResolverService.parse_food_text("xyz")

    async def test_match_food_in_database(
        self, db_session: AsyncSession, seed_test_data
    ):
        """Test fuzzy matching against database."""
        matches = await FoodResolverService.match_food_in_database(
            db_session, "egg", max_results=3
        )

        assert len(matches) > 0
        assert matches[0].food_id is not None
        assert "egg" in matches[0].name.lower()
        assert 0.0 <= matches[0].similarity_score <= 1.0

    async def test_match_food_in_database_no_matches(self, db_session: AsyncSession):
        """Test matching with no results."""
        matches = await FoodResolverService.match_food_in_database(
            db_session, "xyzabc123nonexistent", max_results=3
        )

        assert len(matches) == 0

    async def test_get_meal_by_name(self, db_session: AsyncSession, seed_test_data):
        """Test meal lookup."""
        meal = await FoodResolverService.get_meal_by_name(db_session, "breakfast")

        assert meal is not None
        assert meal.name.lower() == "breakfast"

    async def test_get_meal_by_name_not_found(self, db_session: AsyncSession):
        """Test meal lookup with nonexistent meal."""
        meal = await FoodResolverService.get_meal_by_name(db_session, "nonexistent")

        assert meal is None

    @patch("whati8.services.food_resolver.Anthropic")
    async def test_resolve_foods_integration(
        self, mock_anthropic_class, db_session: AsyncSession, seed_test_data
    ):
        """Test full resolution flow with mocked AI."""
        # Mock Claude API
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "extract_food_items"
        mock_tool_use.input = {
            "items": [
                {
                    "food_name": "egg",
                    "quantity": 2.0,
                    "unit": "pieces",
                    "original_text": "2 eggs",
                    "confidence": 0.95,
                }
            ],
            "meal_detected": "breakfast",
        }
        mock_response.content = [mock_tool_use]
        mock_client.messages.create.return_value = mock_response

        # Call service
        response = await FoodResolverService.resolve_foods(
            db_session, "I had 2 eggs for breakfast", max_matches_per_item=3
        )

        assert response.original_text == "I had 2 eggs for breakfast"
        assert len(response.resolved_items) == 1
        assert response.resolved_items[0].parsed_item.food_name == "egg"
        assert len(response.resolved_items[0].matches) > 0
        assert response.meal_context is not None
        assert response.meal_context.meal_name == "Breakfast"
        assert response.ai_provider == "anthropic"
        assert 0.0 <= response.overall_confidence <= 1.0


@pytest.mark.ai
@pytest.mark.api
@pytest.mark.integration
class TestFoodResolverAPI:
    """Test food resolver API endpoint."""

    @patch("whati8.services.food_resolver.Anthropic")
    async def test_resolve_foods_endpoint_success(
        self,
        mock_anthropic_class,
        authenticated_client: AsyncClient,
        seed_test_data,
    ):
        """Test successful food resolution via API."""
        # Mock Claude API
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "extract_food_items"
        mock_tool_use.input = {
            "items": [
                {
                    "food_name": "egg",
                    "quantity": 2.0,
                    "unit": "pieces",
                    "original_text": "2 eggs",
                    "confidence": 0.95,
                }
            ],
            "meal_detected": "breakfast",
        }
        mock_response.content = [mock_tool_use]
        mock_client.messages.create.return_value = mock_response

        # Call API
        response = await authenticated_client.post(
            "/foods/resolve",
            json={"text": "I had 2 eggs for breakfast", "max_matches_per_item": 3},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["original_text"] == "I had 2 eggs for breakfast"
        assert len(data["resolved_items"]) == 1
        assert data["resolved_items"][0]["parsed_item"]["food_name"] == "egg"
        assert data["ai_provider"] == "anthropic"

    @patch("whati8.services.food_resolver.Anthropic")
    async def test_resolve_foods_endpoint_invalid_input(
        self, mock_anthropic_class, authenticated_client: AsyncClient
    ):
        """Test API with invalid input."""
        # Mock Claude API to return no items
        mock_client = MagicMock()
        mock_anthropic_class.return_value = mock_client

        mock_response = MagicMock()
        mock_tool_use = MagicMock()
        mock_tool_use.type = "tool_use"
        mock_tool_use.name = "extract_food_items"
        mock_tool_use.input = {"items": [], "meal_detected": "unknown"}
        mock_response.content = [mock_tool_use]
        mock_client.messages.create.return_value = mock_response

        response = await authenticated_client.post(
            "/foods/resolve", json={"text": "xyz"}
        )

        assert response.status_code == 400
        # Error response uses {"error": {"message": ...}} format
        error_msg = response.json().get("error", {}).get("message", "") or response.json().get("detail", "")
        assert "extract" in error_msg.lower() or "no food" in error_msg.lower()

    async def test_resolve_foods_endpoint_no_auth(self, client: AsyncClient):
        """Test API without authentication."""
        response = await client.post("/foods/resolve", json={"text": "I had 2 eggs"})

        assert response.status_code == 401

    async def test_resolve_foods_endpoint_empty_text(
        self, authenticated_client: AsyncClient
    ):
        """Test API with empty text."""
        response = await authenticated_client.post("/foods/resolve", json={"text": ""})

        # Should fail validation (min_length=1)
        assert response.status_code == 422


@pytest.mark.unit
class TestFoodResolverSchemas:
    """Test Pydantic schemas for food resolver."""

    def test_food_resolve_request_schema(self):
        """Test request schema validation."""
        request = FoodResolveRequest(
            text="I had 2 eggs",
            meal_hint="breakfast",
            max_matches_per_item=5,
        )

        assert request.text == "I had 2 eggs"
        assert request.meal_hint == "breakfast"
        assert request.max_matches_per_item == 5

    def test_parsed_food_item_schema(self):
        """Test parsed food item schema."""
        item = ParsedFoodItem(
            food_name="egg",
            quantity=2.0,
            unit="pieces",
            original_text="2 eggs",
            confidence=0.95,
        )

        assert item.food_name == "egg"
        assert item.quantity == 2.0
        assert 0.0 <= item.confidence <= 1.0

    def test_parsed_food_item_confidence_validation(self):
        """Test confidence score validation."""
        # Valid confidence
        item = ParsedFoodItem(
            food_name="egg",
            quantity=2.0,
            unit="pieces",
            confidence=0.5,
        )
        assert item.confidence == 0.5

        # Invalid confidence (should be caught by Pydantic)
        with pytest.raises(ValueError):
            ParsedFoodItem(
                food_name="egg",
                quantity=2.0,
                unit="pieces",
                confidence=1.5,  # > 1.0
            )
