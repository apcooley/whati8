"""Service for food units system."""

import re
from difflib import SequenceMatcher
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.models import Food, FoodPortion
from whati8.logging_config import get_logger
from whati8.schemas.food_units import (
    UnitType,
    FoodUnitOption,
    FoodWithUnitsResponse,
    CreateFoodWithUnitsRequest,
)

logger = get_logger(__name__)


class FoodUnitsService:
    """Service for managing food units and portions."""

    # Standard unit conversions
    MASS_CONVERSIONS = {
        "g": 1.0,
        "gram": 1.0,
        "grams": 1.0,
        "oz": 28.35,
        "ounce": 28.35,
        "ounces": 28.35,
        "lb": 453.6,
        "pound": 453.6,
        "pounds": 453.6,
    }

    VOLUME_DEFAULTS = {
        "cup": 237,
        "cups": 237,
        "tbsp": 15,
        "tablespoon": 15,
        "tablespoons": 15,
        "tsp": 5,
        "teaspoon": 5,
        "teaspoons": 5,
        "fl. oz": 30,
        "fl oz": 30,
        "floz": 30,
        "ml": 1,  # 1ml ≈ 1g for water
        "l": 1000,
    }

    UNIT_TYPE_KEYWORDS = {
        "mass": ["g", "gram", "oz", "ounce", "lb", "pound"],
        "volume": ["cup", "tbsp", "tsp", "ml", "l", "oz"],
        "piece": ["piece", "cookie", "egg", "slice", "breast", "item"],
    }

    @staticmethod
    def convert_mass_to_grams(amount: float, unit: str) -> float:
        """Convert mass unit to grams."""
        unit_lower = unit.lower().strip()
        conversion = FoodUnitsService.MASS_CONVERSIONS.get(unit_lower, 1.0)
        return amount * conversion

    @staticmethod
    def get_volume_default_grams(unit: str) -> float:
        """Get default gram weight for volume unit."""
        unit_lower = unit.lower().strip()
        return FoodUnitsService.VOLUME_DEFAULTS.get(unit_lower, 100.0)

    @staticmethod
    def get_piece_default_grams() -> float:
        """Default gram weight for piece unit."""
        return 100.0

    @staticmethod
    def detect_unit_type(user_input: str) -> UnitType:
        """Detect unit type from user input."""
        input_lower = user_input.lower()

        # Check mass units
        for unit in FoodUnitsService.UNIT_TYPE_KEYWORDS["mass"]:
            if unit in input_lower:
                return UnitType.MASS

        # Check volume units
        for unit in FoodUnitsService.UNIT_TYPE_KEYWORDS["volume"]:
            if unit in input_lower:
                return UnitType.VOLUME

        # Check piece units
        for unit in FoodUnitsService.UNIT_TYPE_KEYWORDS["piece"]:
            if unit in input_lower:
                return UnitType.PIECE

        # Default to piece if we can extract a number + word
        # (e.g., "3 cookies" where cookies isn't recognized)
        if re.search(r'\d+\s+\w+', user_input):
            return UnitType.PIECE

        return UnitType.OTHER

    @staticmethod
    def unit_similarity_score(user_unit: str, available_unit: str) -> float:
        """Score similarity between user unit and available unit (0-1)."""
        user_lower = user_unit.lower().strip()
        avail_lower = available_unit.lower().strip()

        # Exact match
        if user_lower == avail_lower:
            return 1.0

        # Singular/plural match
        if user_lower.rstrip("s") == avail_lower.rstrip("s"):
            return 0.95

        # Substring match
        if user_lower in avail_lower or avail_lower in user_lower:
            return 0.8

        # Fuzzy match
        ratio = SequenceMatcher(None, user_lower, avail_lower).ratio()
        return max(0.0, min(1.0, ratio))

    @staticmethod
    async def get_all_units_for_food(
        db: AsyncSession,
        food_id: int,
    ) -> list[FoodUnitOption]:
        """Get all available units/portions for a food."""
        result = await db.execute(
            select(FoodPortion)
            .where(FoodPortion.food_id == food_id)
            .order_by(FoodPortion.gram_weight)
        )
        portions = result.scalars().all()

        options = []
        for p in portions:
            # Determine unit type
            unit_type = FoodUnitsService._classify_unit_type(p.unit_name)

            # Build display name
            unit_display = p.modifier if p.modifier else p.unit_name
            display_name = f"{float(p.amount)} {unit_display} ({float(p.gram_weight)}g)"

            option = FoodUnitOption(
                portion_id=p.id,
                food_id=p.food_id,
                unit_type=unit_type,
                unit_name=p.unit_name,
                modifier=p.modifier,
                amount=float(p.amount),
                gram_weight=float(p.gram_weight),
                display_name=display_name,
                similarity_score=0.0,  # No user input yet
            )
            options.append(option)

        return options

    @staticmethod
    def pick_best_unit(
        units: list[FoodUnitOption],
        user_input: str,
    ) -> FoodUnitOption:
        """Pick the best matching unit based on user input."""
        if not units:
            return None

        # Score each unit
        best_unit = None
        best_score = -1.0

        for unit in units:
            score = FoodUnitsService.unit_similarity_score(user_input, unit.unit_name)
            # Also check modifier
            if unit.modifier:
                score = max(score, FoodUnitsService.unit_similarity_score(user_input, unit.modifier))

            if score > best_score:
                best_score = score
                best_unit = unit

        # Update similarity score on best unit
        if best_unit:
            best_unit.similarity_score = best_score

        return best_unit or units[0]  # Fallback to first

    @staticmethod
    def _classify_unit_type(unit_name: str) -> UnitType:
        """Classify a unit name into a type."""
        unit_lower = unit_name.lower()

        # Mass units
        if any(m in unit_lower for m in ["g", "oz", "lb", "ounce", "pound"]):
            return UnitType.MASS

        # Volume units
        if any(v in unit_lower for v in ["cup", "tbsp", "tsp", "ml", "l", "fl"]):
            return UnitType.VOLUME

        # Piece
        if any(p in unit_lower for p in ["piece", "slice", "breast", "item"]):
            return UnitType.PIECE

        # Default to other
        return UnitType.OTHER

    @staticmethod
    async def create_food_with_units(
        db: AsyncSession,
        user_id: int,
        request: CreateFoodWithUnitsRequest,
    ) -> Food:
        """Create a new food with units/portions."""
        
        # Calculate gram weight based on unit type
        if request.unit_type == UnitType.MASS:
            # Convert to grams
            gram_weight = FoodUnitsService.convert_mass_to_grams(
                request.amount, request.unit_name
            )
        elif request.unit_type == UnitType.VOLUME:
            # Use user-specified or default
            gram_weight = request.gram_weight or FoodUnitsService.get_volume_default_grams(
                request.unit_name
            )
        elif request.unit_type == UnitType.PIECE:
            # Use user-specified or default
            gram_weight = request.gram_weight or FoodUnitsService.get_piece_default_grams()
        else:  # OTHER
            # User must specify
            gram_weight = request.gram_weight or 100.0

        # Create food
        food = Food(
            name=request.name,
            brand=request.brand,
            category=request.category,
            serving_size=gram_weight,  # Primary serving size in grams
            unit="g",  # Always store primary unit as grams
            created_by_user_id=user_id,
        )
        db.add(food)
        await db.flush()  # Get food.id

        # Create portion entry
        portion = FoodPortion(
            food_id=food.id,
            amount=request.amount,
            unit_name=request.unit_name,
            modifier=None,
            gram_weight=gram_weight,
        )
        db.add(portion)

        # If mass unit, also add gram-based portion for convenience
        if request.unit_type == UnitType.MASS and request.unit_name.lower() != "g":
            gram_portion = FoodPortion(
                food_id=food.id,
                amount=gram_weight,
                unit_name="g",
                modifier=None,
                gram_weight=gram_weight,
            )
            db.add(gram_portion)

        await db.commit()
        await db.refresh(food)

        logger.info(
            f"Created food: {food.name} ({request.amount} {request.unit_name} = {gram_weight}g)"
        )
        return food

    @staticmethod
    async def add_unit_to_food(
        db: AsyncSession,
        food_id: int,
        unit_type: UnitType,
        unit_name: str,
        amount: float,
        gram_weight: float,
    ) -> FoodPortion:
        """Add another unit/portion to an existing food."""
        
        portion = FoodPortion(
            food_id=food_id,
            amount=amount,
            unit_name=unit_name,
            modifier=None,
            gram_weight=gram_weight,
        )
        db.add(portion)
        await db.commit()
        await db.refresh(portion)

        logger.info(
            f"Added unit to food {food_id}: {amount} {unit_name} = {gram_weight}g"
        )
        return portion

    @staticmethod
    async def get_food_with_units(
        db: AsyncSession,
        food_id: int,
    ) -> FoodWithUnitsResponse:
        """Get food with all available units."""
        result = await db.execute(
            select(Food)
            .where(Food.id == food_id)
            .options(selectinload(Food.portions))
        )
        food = result.scalar_one_or_none()

        if not food:
            return None

        units = await FoodUnitsService.get_all_units_for_food(db, food_id)

        return FoodWithUnitsResponse(
            id=food.id,
            name=food.name,
            brand=food.brand,
            category=food.category,
            units=units,
            recommended_unit=units[0] if units else None,  # Backend doesn't pick; agent does
        )
