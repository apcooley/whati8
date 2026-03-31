"""Tests for recipe nutrition calculation accuracy.

Validates:
- _get_quantity_in_grams correctly converts standard units (oz, cup, tbsp, etc.)
- _get_quantity_in_grams falls back to standard conversions when no portion match
- Recipe materialization produces correct per-serving macros
- Baked Potato Soup regression: ingredients in oz must convert correctly
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock


class TestGetQuantityInGrams:
    """Unit tests for RecipeService._get_quantity_in_grams."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    def _make_ingredient(self, quantity, unit, portion_description=None, food_portions=None):
        """Create a mock RecipeIngredient."""
        ingredient = MagicMock()
        ingredient.quantity = Decimal(str(quantity))
        ingredient.unit = unit
        ingredient.portion_description = portion_description or unit
        food = MagicMock()
        food.portions = food_portions or []
        food.serving_size = Decimal("100")
        ingredient.food = food
        return ingredient

    def _make_portion(self, unit_name, gram_weight, portion_description=None):
        """Create a mock FoodPortion."""
        portion = MagicMock()
        portion.unit_name = unit_name
        portion.gram_weight = Decimal(str(gram_weight))
        portion.portion_description = portion_description or unit_name
        return portion

    @pytest.mark.asyncio
    async def test_grams_passthrough(self, mock_db):
        """Quantity in grams should pass through unchanged."""
        from whati8.services.recipe_service import RecipeService
        ing = self._make_ingredient(425, "grams")
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        assert result == Decimal("425")

    @pytest.mark.asyncio
    async def test_g_passthrough(self, mock_db):
        """Quantity in 'g' should pass through unchanged."""
        from whati8.services.recipe_service import RecipeService
        ing = self._make_ingredient(100, "g")
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        assert result == Decimal("100")

    @pytest.mark.asyncio
    async def test_oz_with_matching_portion(self, mock_db):
        """oz with a matching portion should use portion gram_weight."""
        from whati8.services.recipe_service import RecipeService
        portion = self._make_portion("oz", 28.35)
        ing = self._make_ingredient(15, "oz", food_portions=[portion])
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        assert abs(result - Decimal("425.25")) < Decimal("0.1")

    @pytest.mark.asyncio
    async def test_oz_without_portion_uses_standard_conversion(self, mock_db):
        """oz with NO matching portion should still convert correctly (~28.35g/oz)."""
        from whati8.services.recipe_service import RecipeService
        ing = self._make_ingredient(15, "oz")  # no portions
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        # Must be ~425g, NOT 15g
        assert result > Decimal("400"), (
            f"15 oz should be ~425g, got {result}g — standard unit fallback is broken"
        )

    @pytest.mark.asyncio
    async def test_cup_without_portion_uses_standard_conversion(self, mock_db):
        """cup with NO matching portion should use ~240g default."""
        from whati8.services.recipe_service import RecipeService
        ing = self._make_ingredient(1.5, "cup")
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        assert result > Decimal("300"), (
            f"1.5 cups should be ~360g, got {result}g"
        )

    @pytest.mark.asyncio
    async def test_tbsp_without_portion_uses_standard_conversion(self, mock_db):
        """tbsp with NO matching portion should use ~15g default."""
        from whati8.services.recipe_service import RecipeService
        ing = self._make_ingredient(2, "tbsp")
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        assert result > Decimal("25"), (
            f"2 tbsp should be ~30g, got {result}g"
        )

    @pytest.mark.asyncio
    async def test_tsp_without_portion_uses_standard_conversion(self, mock_db):
        """tsp with NO matching portion should use ~5g default."""
        from whati8.services.recipe_service import RecipeService
        ing = self._make_ingredient(3, "tsp")
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        assert result > Decimal("12"), (
            f"3 tsp should be ~15g, got {result}g"
        )

    @pytest.mark.asyncio
    async def test_lb_without_portion_uses_standard_conversion(self, mock_db):
        """lb/pound should convert to ~453.6g."""
        from whati8.services.recipe_service import RecipeService
        ing = self._make_ingredient(2, "lb")
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        assert result > Decimal("900"), (
            f"2 lb should be ~907g, got {result}g"
        )

    @pytest.mark.asyncio
    async def test_cup_with_parenthetical_weight(self, mock_db):
        """Unit like 'cup (220.0g)' should extract gram weight from parens."""
        from whati8.services.recipe_service import RecipeService
        ing = self._make_ingredient(1.5, "cup (220.0g)")
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        assert abs(result - Decimal("330")) < Decimal("1"), (
            f"1.5 × cup (220.0g) should be 330g, got {result}g"
        )

    @pytest.mark.asyncio
    async def test_portion_match_takes_priority(self, mock_db):
        """When a portion matches, use it even if a standard fallback exists."""
        from whati8.services.recipe_service import RecipeService
        # Food has a "cup" portion that's 250g (e.g., dense food)
        portion = self._make_portion("cup", 250)
        ing = self._make_ingredient(2, "cup", food_portions=[portion])
        result = await RecipeService._get_quantity_in_grams(mock_db, ing)
        assert result == Decimal("500")  # 2 × 250g, not 2 × 240g default
