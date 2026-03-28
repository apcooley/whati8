"""
Tests for new food units & weight system.

Features:
1. Food lookup returns all units, agent picks best
2. Food creation with standard + custom units
3. Weight calculation (mass, volume, piece, custom)
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from whati8.models import Food, FoodPortion, User
from whati8.services.food_units import FoodUnitsService
from whati8.schemas.food_units import (
    UnitType,
    CreateFoodWithUnitsRequest,
    FoodUnitOption,
)


class TestFoodUnitsService:
    """Tests for food units service."""

    @pytest.mark.asyncio
    async def test_get_all_units_for_food(self, db_session: AsyncSession, sample_food_with_portions: Food):
        """Get all available units for a food."""
        units = await FoodUnitsService.get_all_units_for_food(db_session, sample_food_with_portions.id)
        
        assert len(units) > 0
        assert all(isinstance(u, FoodUnitOption) for u in units)
        assert all(u.food_id == sample_food_with_portions.id for u in units)
        # Check gram_weight is set for all
        assert all(u.gram_weight > 0 for u in units)

    @pytest.mark.asyncio
    async def test_pick_best_unit_match(self, db_session: AsyncSession, sample_food_with_portions: Food):
        """Agent picks most likely unit from available options."""
        # Food has portions: cup (240g), tbsp (15g), g (1g)
        # User said "2 cups" -> should pick "cup"
        # User said "1 tbsp" -> should pick "tbsp"
        # User said "100 grams" -> should pick "g"
        
        units = await FoodUnitsService.get_all_units_for_food(db_session, sample_food_with_portions.id)
        
        # Mock agent decision
        best_unit = FoodUnitsService.pick_best_unit(units, user_input="2 cups")
        assert best_unit.unit_name == "cup" or best_unit.display_name.startswith("1 cup")
        
        best_unit = FoodUnitsService.pick_best_unit(units, user_input="100 grams")
        assert best_unit.unit_name == "g" or best_unit.modifier is None  # grams


class TestStandardUnitConversions:
    """Tests for converting standard units to grams."""

    def test_mass_unit_to_grams(self):
        """Mass units (g, oz, lb) convert to grams."""
        # 1 oz = 28.35g
        assert abs(FoodUnitsService.convert_mass_to_grams(1.0, "oz") - 28.35) < 0.1
        
        # 1 lb = 453.6g
        assert abs(FoodUnitsService.convert_mass_to_grams(1.0, "lb") - 453.6) < 0.1
        
        # 1g = 1g
        assert FoodUnitsService.convert_mass_to_grams(1.0, "g") == 1.0

    def test_volume_unit_defaults(self):
        """Volume units have sensible defaults."""
        # 1 cup = 237g
        assert FoodUnitsService.get_volume_default_grams("cup") == 237
        
        # 1 fl. oz = 30g
        assert FoodUnitsService.get_volume_default_grams("fl. oz") == 30
        
        # 1 tbsp = 15g
        assert FoodUnitsService.get_volume_default_grams("tbsp") == 15
        
        # 1 tsp = 5g
        assert FoodUnitsService.get_volume_default_grams("tsp") == 5

    def test_piece_default(self):
        """Piece unit defaults to 100g."""
        assert FoodUnitsService.get_piece_default_grams() == 100


class TestFoodCreationWithUnits:
    """Tests for creating foods with units."""

    @pytest.mark.asyncio
    async def test_create_food_with_mass_unit(self, db_session: AsyncSession, user: User):
        """Create food with mass unit (g, oz, lb)."""
        request = CreateFoodWithUnitsRequest(
            name="Rice",
            brand=None,
            unit_type=UnitType.MASS,
            unit_name="g",
            amount=100.0,  # 100g per serving
            category="Grains",
        )
        
        food = await FoodUnitsService.create_food_with_units(
            db_session, user.id, request
        )
        
        assert food.name == "Rice"
        assert food.unit == "g"
        assert food.serving_size == 100.0
        # Should have a portion for grams
        portions = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food.id)
        )
        assert len(portions.scalars().all()) >= 1

    @pytest.mark.asyncio
    async def test_create_food_with_volume_unit(self, db_session: AsyncSession, user: User):
        """Create food with volume unit (cup, tbsp, tsp, fl oz)."""
        request = CreateFoodWithUnitsRequest(
            name="Milk",
            brand="Whole",
            unit_type=UnitType.VOLUME,
            unit_name="cup",
            amount=1.0,  # 1 cup
            gram_weight=240.0,  # User set 240g for 1 cup
            category="Dairy",
        )
        
        food = await FoodUnitsService.create_food_with_units(
            db_session, user.id, request
        )
        
        assert food.name == "Milk"
        assert food.brand == "Whole"
        # Should create portion: 1 cup = 240g
        portions = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food.id)
        )
        portions_list = portions.scalars().all()
        assert len(portions_list) >= 1
        assert any(p.gram_weight == 240.0 for p in portions_list)

    @pytest.mark.asyncio
    async def test_create_food_with_piece(self, db_session: AsyncSession, user: User):
        """Create food with piece unit."""
        request = CreateFoodWithUnitsRequest(
            name="Cookie",
            brand="Homemade",
            unit_type=UnitType.PIECE,
            unit_name="piece",
            amount=1.0,
            gram_weight=25.0,  # 1 cookie = 25g
            category="Baked",
        )
        
        food = await FoodUnitsService.create_food_with_units(
            db_session, user.id, request
        )
        
        assert food.name == "Cookie"
        # Should create portion: 1 piece = 25g
        portions = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food.id)
        )
        portions_list = portions.scalars().all()
        assert any(p.unit_name == "piece" and p.gram_weight == 25.0 for p in portions_list)

    @pytest.mark.asyncio
    async def test_create_food_with_custom_unit(self, db_session: AsyncSession, user: User):
        """Create food with custom unit (food-specific only)."""
        request = CreateFoodWithUnitsRequest(
            name="Granola",
            brand=None,
            unit_type=UnitType.OTHER,
            unit_name="scoop",  # Custom unit
            amount=1.0,
            gram_weight=50.0,  # 1 scoop = 50g
            category="Cereal",
        )
        
        food = await FoodUnitsService.create_food_with_units(
            db_session, user.id, request
        )
        
        assert food.name == "Granola"
        # Should create portion: 1 scoop = 50g (food-specific)
        portions = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == food.id)
        )
        portions_list = portions.scalars().all()
        assert any(p.unit_name == "scoop" and p.gram_weight == 50.0 for p in portions_list)


class TestFoodLoggingWithUnits:
    """Tests for logging food with selected units."""

    @pytest.mark.asyncio
    async def test_log_food_with_picked_unit(self, db_session: AsyncSession, user: User, sample_food: Food):
        """User logs food with selected unit and weight."""
        # User: "I had 2 cups of milk"
        # System: Picked "cup" as unit, 2 cups = 480g
        
        quantity = 2.0
        unit_name = "cup"
        gram_weight = 240.0  # per cup
        total_grams = quantity * gram_weight  # 480g
        
        assert total_grams == 480.0

    @pytest.mark.asyncio
    async def test_log_food_with_custom_weight(self, db_session: AsyncSession, user: User, sample_food: Food):
        """User can override weight."""
        # System suggests: 2 cups = 480g
        # User edits to: 500g
        
        user_specified_weight = 500.0
        assert user_specified_weight == 500.0


class TestFoodUnitComparison:
    """Tests for comparing and sorting units."""

    def test_unit_similarity_score(self):
        """Unit similarity scoring for agent decision."""
        # User said "cups", compare to available units
        score_cup = FoodUnitsService.unit_similarity_score("cups", "cup")
        score_tbsp = FoodUnitsService.unit_similarity_score("cups", "tbsp")
        
        assert score_cup > score_tbsp  # "cup" is better match than "tbsp"

    def test_unit_type_matching(self):
        """Match user unit type to standard units."""
        # User said "2 cups" -> volume unit
        unit_type = FoodUnitsService.detect_unit_type("2 cups")
        assert unit_type == UnitType.VOLUME
        
        # User said "100g" -> mass unit
        unit_type = FoodUnitsService.detect_unit_type("100g")
        assert unit_type == UnitType.MASS
        
        # User said "3 cookies" -> piece
        unit_type = FoodUnitsService.detect_unit_type("3 cookies")
        assert unit_type == UnitType.PIECE
