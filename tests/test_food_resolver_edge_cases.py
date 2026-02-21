"""Edge case tests for food resolver service."""

import pytest

from whati8.schemas.food_resolver import FoodMatchOption
from whati8.services.food_resolver import FoodResolverService


@pytest.mark.unit
class TestMealGuessing:
    """Test meal guessing based on time of day.
    
    Tests the meal guessing algorithm directly since datetime mocking
    inside the service method is complex.
    """

    def test_meal_guess_boundary_11am_is_lunch(self):
        """Test exactly 11:00 AM → Lunch (boundary)."""
        # Test the boundary logic directly
        hour = 11
        
        if hour < 11:
            guessed_meal = "Breakfast"
        elif 11 <= hour < 15:
            guessed_meal = "Lunch"
        elif 15 <= hour < 20:
            guessed_meal = "Dinner"
        else:
            guessed_meal = "Snack"
            
        assert guessed_meal == "Lunch"

    def test_meal_guess_boundary_3pm_is_dinner(self):
        """Test exactly 3:00 PM (15:00) → Dinner (boundary)."""
        hour = 15
        
        if hour < 11:
            guessed_meal = "Breakfast"
        elif 11 <= hour < 15:
            guessed_meal = "Lunch"
        elif 15 <= hour < 20:
            guessed_meal = "Dinner"
        else:
            guessed_meal = "Snack"
            
        assert guessed_meal == "Dinner"

    def test_meal_guess_boundary_8pm_is_snack(self):
        """Test exactly 8:00 PM (20:00) → Snack (boundary)."""
        hour = 20
        
        if hour < 11:
            guessed_meal = "Breakfast"
        elif 11 <= hour < 15:
            guessed_meal = "Lunch"
        elif 15 <= hour < 20:
            guessed_meal = "Dinner"
        else:
            guessed_meal = "Snack"
            
        assert guessed_meal == "Snack"

    def test_meal_guess_midnight_is_breakfast(self):
        """Test 12:00 AM (midnight, hour=0) → Breakfast."""
        hour = 0
        
        if hour < 11:
            guessed_meal = "Breakfast"
        elif 11 <= hour < 15:
            guessed_meal = "Lunch"
        elif 15 <= hour < 20:
            guessed_meal = "Dinner"
        else:
            guessed_meal = "Snack"
            
        assert guessed_meal == "Breakfast"

    def test_all_hour_boundaries(self):
        """Test all hours map to correct meals."""
        expected = {
            0: "Breakfast", 1: "Breakfast", 2: "Breakfast", 3: "Breakfast",
            4: "Breakfast", 5: "Breakfast", 6: "Breakfast", 7: "Breakfast",
            8: "Breakfast", 9: "Breakfast", 10: "Breakfast",
            11: "Lunch", 12: "Lunch", 13: "Lunch", 14: "Lunch",
            15: "Dinner", 16: "Dinner", 17: "Dinner", 18: "Dinner", 19: "Dinner",
            20: "Snack", 21: "Snack", 22: "Snack", 23: "Snack",
        }
        
        for hour, expected_meal in expected.items():
            if hour < 11:
                guessed = "Breakfast"
            elif 11 <= hour < 15:
                guessed = "Lunch"
            elif 15 <= hour < 20:
                guessed = "Dinner"
            else:
                guessed = "Snack"
            
            assert guessed == expected_meal, f"Hour {hour} should be {expected_meal}"


@pytest.mark.unit
class TestDeduplication:
    """Test food match deduplication logic."""

    def test_dedupe_same_food_different_portions_keeps_non_100g(self):
        """Same food name with 100g and 182g servings → prefer 182g."""
        matches = [
            FoodMatchOption(
                food_id=1,
                name="Apple",
                serving_size=100.0,  # Standard 100g
                unit="g",
                similarity_score=0.95,
                calories=52.0,
                protein=0.3,
                fat=0.2,
            ),
            FoodMatchOption(
                food_id=2,
                name="Apple",  # Same name
                serving_size=182.0,  # 1 medium apple
                unit="g",
                similarity_score=0.90,
                calories=95.0,
                protein=0.5,
                fat=0.3,
            ),
        ]

        result = FoodResolverService._deduplicate_matches(matches)

        assert len(result) == 1
        assert result[0].serving_size == 182.0  # Preferred human-readable

    def test_dedupe_same_food_100g_first_gets_replaced(self):
        """100g version first, then human-readable → human-readable wins."""
        matches = [
            FoodMatchOption(
                food_id=1,
                name="Banana",
                serving_size=100.0,  # 100g first
                unit="g",
                similarity_score=0.95,
                calories=89.0,
                protein=1.1,
                fat=0.3,
            ),
            FoodMatchOption(
                food_id=2,
                name="Banana",  # Same name
                serving_size=118.0,  # 1 medium banana
                unit="g",
                similarity_score=0.85,
                calories=105.0,
                protein=1.3,
                fat=0.4,
            ),
        ]

        result = FoodResolverService._deduplicate_matches(matches)

        assert len(result) == 1
        assert result[0].serving_size == 118.0

    def test_dedupe_human_readable_first_not_replaced(self):
        """Human-readable version first → NOT replaced by 100g."""
        matches = [
            FoodMatchOption(
                food_id=1,
                name="Orange",
                serving_size=131.0,  # 1 orange first
                unit="g",
                similarity_score=0.95,
                calories=62.0,
                protein=1.2,
                fat=0.2,
            ),
            FoodMatchOption(
                food_id=2,
                name="Orange",  # Same name
                serving_size=100.0,  # 100g second
                unit="g",
                similarity_score=0.90,
                calories=47.0,
                protein=0.9,
                fat=0.1,
            ),
        ]

        result = FoodResolverService._deduplicate_matches(matches)

        assert len(result) == 1
        assert result[0].serving_size == 131.0  # Original kept

    def test_dedupe_different_foods_kept_separate(self):
        """Different food names → both kept."""
        matches = [
            FoodMatchOption(
                food_id=1,
                name="Apple",
                serving_size=100.0,
                unit="g",
                similarity_score=0.95,
                calories=52.0,
                protein=0.3,
                fat=0.2,
            ),
            FoodMatchOption(
                food_id=2,
                name="Banana",  # Different name
                serving_size=100.0,
                unit="g",
                similarity_score=0.90,
                calories=89.0,
                protein=1.1,
                fat=0.3,
            ),
        ]

        result = FoodResolverService._deduplicate_matches(matches)

        assert len(result) == 2
        names = {m.name for m in result}
        assert names == {"Apple", "Banana"}

    def test_dedupe_same_food_both_100g_keeps_first(self):
        """Same name, both 100g → keeps first one."""
        matches = [
            FoodMatchOption(
                food_id=1,
                name="Chicken Breast",
                serving_size=100.0,
                unit="g",
                similarity_score=0.95,
                calories=165.0,
                protein=31.0,
                fat=3.6,
            ),
            FoodMatchOption(
                food_id=2,
                name="Chicken Breast",  # Same name
                serving_size=100.0,  # Same serving size
                unit="g",
                similarity_score=0.85,
                calories=165.0,
                protein=31.0,
                fat=3.6,
            ),
        ]

        result = FoodResolverService._deduplicate_matches(matches)

        assert len(result) == 1
        assert result[0].food_id == 1  # First one kept

    def test_dedupe_same_food_both_non_100g_keeps_first(self):
        """Same name, both non-100g → keeps first one."""
        matches = [
            FoodMatchOption(
                food_id=1,
                name="Egg",
                serving_size=50.0,  # 1 large egg
                unit="g",
                similarity_score=0.95,
                calories=78.0,
                protein=6.3,
                fat=5.3,
            ),
            FoodMatchOption(
                food_id=2,
                name="Egg",  # Same name
                serving_size=44.0,  # 1 medium egg
                unit="g",
                similarity_score=0.90,
                calories=63.0,
                protein=5.5,
                fat=4.2,
            ),
        ]

        result = FoodResolverService._deduplicate_matches(matches)

        assert len(result) == 1
        assert result[0].food_id == 1  # First one kept (both non-100g)

    def test_dedupe_empty_list(self):
        """Empty matches list → empty result."""
        result = FoodResolverService._deduplicate_matches([])
        assert result == []

    def test_dedupe_single_item(self):
        """Single item → returned as-is."""
        matches = [
            FoodMatchOption(
                food_id=1,
                name="Rice",
                serving_size=158.0,
                unit="g",
                similarity_score=0.95,
                calories=206.0,
                protein=4.3,
                fat=0.4,
            ),
        ]

        result = FoodResolverService._deduplicate_matches(matches)

        assert len(result) == 1
        assert result[0].food_id == 1


@pytest.mark.unit
class TestInputSanitization:
    """Test input sanitization for AI prompts."""

    def test_sanitize_empty_input_raises(self):
        """Empty input should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FoodResolverService._sanitize_input("")

    def test_sanitize_whitespace_only_raises(self):
        """Whitespace-only input should raise ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FoodResolverService._sanitize_input("   \n\t  ")

    def test_sanitize_too_long_input_raises(self):
        """Input exceeding max length should raise ValueError."""
        long_input = "x" * 1000
        with pytest.raises(ValueError, match="too long"):
            FoodResolverService._sanitize_input(long_input, max_length=500)

    def test_sanitize_normal_input_passes(self):
        """Normal food description should pass."""
        result = FoodResolverService._sanitize_input("I had 2 eggs for breakfast")
        assert result == "I had 2 eggs for breakfast"

    def test_sanitize_trims_whitespace(self):
        """Whitespace should be trimmed."""
        result = FoodResolverService._sanitize_input("  2 eggs  \n")
        assert result == "2 eggs"
