"""
Test suite for duplicate quantity bug in food display.

Bug: Built Puff bars show "11 Bar" instead of "1 Bar", 
crackers show "6 6 crackers" instead of "6 crackers",
grams show "1113g" instead of "113g".

Root cause: getServingLabel() concatenates quantity + unit,
but default_unit already includes quantity in some cases.
"""

import pytest
from datetime import datetime
from whati8.schemas.food import FoodResponse
from whati8.schemas.user_food import UserFoodResponse


def mock_food(food_id: int = 1, name: str = "Test Food") -> FoodResponse:
    """Create a mock food for testing."""
    return FoodResponse(
        id=food_id,
        name=name,
        brand=None,
        serving_size=100.0,
        unit="g",
        food_nutrients=[],
        portions=[],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


def mock_user_food(
    food: FoodResponse,
    default_quantity: float = 1.0,
    default_unit: str = "g",
    nickname: str | None = None,
) -> UserFoodResponse:
    """Create a mock user_food for testing."""
    return UserFoodResponse(
        id=1,
        user_id=1,
        food_id=food.id,
        nickname=nickname,
        default_quantity=default_quantity,
        default_unit=default_unit,
        default_meal_id=None,
        is_favorite=False,
        use_count=0,
        last_used_at=None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        food=food,
        default_meal=None,
    )


def get_serving_label(uf: UserFoodResponse) -> str:
    """
    Get default serving label e.g. "2 piece" or "100 g".
    
    FIXED: Detect if default_unit already starts with a quantity
    to avoid duplication like "1 1 Bar" or "6 6 crackers".
    """
    qty = uf.default_quantity if uf.default_quantity is not None else uf.food.serving_size
    unit = uf.default_unit or uf.food.unit
    
    # If unit starts with a digit, it already includes quantity
    # Examples: "1 Bar (44g)", "6 crackers (28g)", "113g"
    if unit and unit[0].isdigit():
        return unit
    
    # Format quantity: remove .0 for whole numbers
    qty_str = str(int(qty)) if qty == int(qty) else str(qty)
    
    # Otherwise prepend quantity
    return f"{qty_str} {unit}"


class TestDuplicateQuantityBug:
    """Test cases for the duplicate quantity display bug."""

    def test_bar_with_quantity_prefix(self):
        """1 Bar (44g) should display as "1 Bar (44g)", not "1 1 Bar (44g)"."""
        food = mock_food(name="Built Puff Bar")
        uf = mock_user_food(food, default_quantity=1.0, default_unit="1 Bar (44g)")
        
        label = get_serving_label(uf)
        
        assert label == "1 Bar (44g)"
        assert not label.startswith("1 1")
        assert label.count(" 1 ") == 0  # No double "1"

    def test_crackers_with_quantity_prefix(self):
        """6 crackers (28g) should display as "6 crackers (28g)", not "6 6 crackers (28g)"."""
        food = mock_food(name="Crackers")
        uf = mock_user_food(food, default_quantity=6.0, default_unit="6 crackers (28g)")
        
        label = get_serving_label(uf)
        
        assert label == "6 crackers (28g)"
        assert not label.startswith("6 6")
        assert label.count(" 6 ") == 0  # No double "6"

    def test_grams_with_quantity_prefix(self):
        """113g should display as "113g", not "1113g"."""
        food = mock_food(name="Food in grams")
        uf = mock_user_food(food, default_quantity=1.0, default_unit="113g")
        
        label = get_serving_label(uf)
        
        assert label == "113g"
        assert label != "1113g"

    def test_unit_without_quantity_prefix(self):
        """bottle (325g) with qty=1 should display as "1 bottle (325g)"."""
        food = mock_food(name="Protein Shake")
        uf = mock_user_food(food, default_quantity=1.0, default_unit="bottle (325g)")
        
        label = get_serving_label(uf)
        
        assert label == "1 bottle (325g)"
        assert label.startswith("1 ")

    def test_plain_grams_without_prefix(self):
        """grams with qty=100 should display as "100 grams"."""
        food = mock_food(name="Oats")
        uf = mock_user_food(food, default_quantity=100.0, default_unit="grams")
        
        label = get_serving_label(uf)
        
        assert label == "100 grams"

    def test_slices_without_quantity_prefix(self):
        """slices (14g) with qty=4 should display as "4 slices (14g)"."""
        food = mock_food(name="Cheese")
        uf = mock_user_food(food, default_quantity=4.0, default_unit="slices (14g)")
        
        label = get_serving_label(uf)
        
        assert label == "4 slices (14g)"

    def test_roll_without_quantity_prefix(self):
        """roll (43g) with qty=1 should display as "1 roll (43g)"."""
        food = mock_food(name="Sushi Roll")
        uf = mock_user_food(food, default_quantity=1.0, default_unit="roll (43g)")
        
        label = get_serving_label(uf)
        
        assert label == "1 roll (43g)"

    def test_bun_with_quantity_prefix(self):
        """1 Bun (43g) should display as "1 Bun (43g)", not "1 1 Bun (43g)"."""
        food = mock_food(name="Hamburger Bun")
        uf = mock_user_food(food, default_quantity=1.0, default_unit="1 Bun (43g)")
        
        label = get_serving_label(uf)
        
        assert label == "1 Bun (43g)"
        assert not label.startswith("1 1")

    def test_weight_only_format(self):
        """32g (weight only) should display as "32g", not "132g"."""
        food = mock_food(name="Snack")
        uf = mock_user_food(food, default_quantity=1.0, default_unit="32g")
        
        label = get_serving_label(uf)
        
        assert label == "32g"
        assert label != "132g"

    def test_empty_unit_fallback(self):
        """Empty default_unit should fallback to food.unit."""
        food = mock_food(name="Generic Food")
        uf = mock_user_food(food, default_quantity=1.0, default_unit="")
        
        label = get_serving_label(uf)
        
        assert label == "1 g"  # Falls back to food.unit

    def test_none_unit_fallback(self):
        """None default_unit should fallback to food.unit."""
        food = mock_food(name="Generic Food")
        uf = mock_user_food(food, default_quantity=1.0, default_unit=None)
        
        label = get_serving_label(uf)
        
        assert label == "1 g"  # Falls back to food.unit

    def test_decimal_quantity_in_unit(self):
        """1.5 cups (360g) should display as-is, not "1 1.5 cups (360g)"."""
        food = mock_food(name="Milk")
        uf = mock_user_food(food, default_quantity=1.5, default_unit="1.5 cups (360g)")
        
        label = get_serving_label(uf)
        
        assert label == "1.5 cups (360g)"
        assert not label.startswith("1.5 1.5")

    def test_zero_quantity_edge_case(self):
        """Zero quantity should still work (edge case)."""
        food = mock_food(name="Test")
        uf = mock_user_food(food, default_quantity=0.0, default_unit="portion")
        
        label = get_serving_label(uf)
        
        assert label == "0 portion"


class TestServingLabelIntegration:
    """Integration tests using real data patterns from the database."""

    @pytest.mark.parametrize("default_quantity,default_unit,expected", [
        # Real examples from user_foods table
        (1.0, "1 Bar (44g)", "1 Bar (44g)"),
        (6.0, "6 crackers (28g)", "6 crackers (28g)"),
        (1.0, "113g", "113g"),
        (1.0, "32g", "32g"),
        (1.0, "bottle (325g)", "1 bottle (325g)"),
        (1.0, "roll (43g)", "1 roll (43g)"),
        (4.0, "slices (14g)", "4 slices (14g)"),
        (100.0, "grams", "100 grams"),
        (1.0, "1 Bun (43g)", "1 Bun (43g)"),
        (1.0, "1 Bar (40g)", "1 Bar (40g)"),
        (1.0, "1 Bar (43g)", "1 Bar (43g)"),
        (1.0, "1 Bar (44g)", "1 Bar (44g)"),
    ])
    def test_real_world_patterns(self, default_quantity, default_unit, expected):
        """Test against real patterns found in user_foods table."""
        food = mock_food()
        uf = mock_user_food(food, default_quantity=default_quantity, default_unit=default_unit)
        
        label = get_serving_label(uf)
        
        assert label == expected
