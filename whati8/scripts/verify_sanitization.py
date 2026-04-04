"""
Verification script for sanitized food data.

Validates that sanitized_* columns on foods match their source food_nutrients data.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.models.food import Food
from whati8.models.food_nutrient import FoodNutrient
from whati8.scripts.sanitize_foods import (
    CARB_DIFFERENCE,
    CARB_SUMMATION,
    ENERGY_ATWATER_GENERAL,
    ENERGY_ATWATER_SPECIFIC,
    ENERGY_PLAIN,
    FAT,
    FIBER,
    PROTEIN,
)

TOLERANCE = Decimal("0.01")


def _diff_exceeds_tolerance(actual: Decimal | None, expected: Decimal | None) -> bool:
    """Return True if values mismatch beyond tolerance.

    - Both None: OK (no mismatch)
    - One None, one has value: mismatch
    - Both have values: compare with tolerance
    """
    if actual is None and expected is None:
        return False
    if actual is None or expected is None:
        return True  # One side has a value, the other doesn't
    return abs(actual - expected) > TOLERANCE


async def verify_sanitization(db: AsyncSession) -> dict:
    """
    Validate that sanitized_* columns on foods match their source food_nutrients data.

    Returns a dict with:
        usda_checked: Number of USDA foods checked
        usda_failures: Number of USDA foods with mismatched values
        custom_checked: Number of custom foods checked
        custom_failures: Number of custom foods with mismatched values
        null_calories_usda: Number of USDA foods with NULL sanitized_calories
        incomplete_count: Number of foods with is_complete=False
        failures: List of failure dicts, each with at least 'name' and 'reason' keys
    """
    failures: list[dict] = []
    usda_checked = 0
    usda_failures = 0
    custom_checked = 0
    custom_failures = 0
    null_calories_usda = 0

    # ---- USDA foods ----
    usda_result = await db.execute(
        select(Food)
        .where(Food.usda_fdc_id.is_not(None))
        .options(
            selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient)
        )
    )
    usda_foods = usda_result.scalars().all()

    for food in usda_foods:
        usda_checked += 1

        # Check null calories
        if food.sanitized_calories is None:
            null_calories_usda += 1

        # Build nutrient map
        nutrient_map: dict[str, Decimal] = {}
        for fn in food.food_nutrients:
            if fn.nutrient:
                nutrient_map[fn.nutrient.name] = fn.amount_per_serving

        # Compute expected values using the same coalescing logic
        if ENERGY_ATWATER_GENERAL in nutrient_map:
            expected_calories = nutrient_map[ENERGY_ATWATER_GENERAL]
        elif ENERGY_ATWATER_SPECIFIC in nutrient_map:
            expected_calories = nutrient_map[ENERGY_ATWATER_SPECIFIC]
        elif ENERGY_PLAIN in nutrient_map:
            expected_calories = nutrient_map[ENERGY_PLAIN]
        else:
            expected_calories = None

        if CARB_SUMMATION in nutrient_map:
            expected_carbs = nutrient_map[CARB_SUMMATION]
        elif CARB_DIFFERENCE in nutrient_map:
            expected_carbs = nutrient_map[CARB_DIFFERENCE]
        else:
            expected_carbs = None

        expected_protein = nutrient_map.get(PROTEIN)
        expected_fat = nutrient_map.get(FAT)
        expected_fiber = nutrient_map.get(FIBER)

        # Check each field
        food_failed = False
        reasons: list[str] = []

        checks = [
            ("calories", food.sanitized_calories, expected_calories),
            ("protein", food.sanitized_protein, expected_protein),
            ("carbs", food.sanitized_carbs, expected_carbs),
            ("fat", food.sanitized_fat, expected_fat),
            ("fiber", food.sanitized_fiber, expected_fiber),
        ]

        for field, actual, expected in checks:
            if _diff_exceeds_tolerance(actual, expected):
                food_failed = True
                reasons.append(
                    f"{field}: sanitized={actual}, expected={expected}"
                )

        if food_failed:
            usda_failures += 1
            failures.append({
                "name": food.name,
                "reason": "; ".join(reasons),
                "food_id": food.id,
                "type": "usda",
            })

    # ---- Custom foods ----
    custom_result = await db.execute(
        select(Food)
        .where(
            Food.created_by_user_id.is_not(None),
            Food.recipe_id.is_(None),
            Food.usda_fdc_id.is_(None),
        )
        .options(
            selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient)
        )
    )
    custom_foods = custom_result.scalars().all()

    for food in custom_foods:
        custom_checked += 1

        # Build nutrient map
        nutrient_map = {}
        for fn in food.food_nutrients:
            if fn.nutrient:
                nutrient_map[fn.nutrient.name] = fn.amount_per_serving

        # Custom foods use direct mapping (no coalescing)
        expected_calories = nutrient_map.get(ENERGY_PLAIN)
        expected_protein = nutrient_map.get(PROTEIN)
        expected_carbs = nutrient_map.get(CARB_DIFFERENCE)
        expected_fat = nutrient_map.get(FAT)
        expected_fiber = nutrient_map.get(FIBER)

        food_failed = False
        reasons = []

        checks = [
            ("calories", food.sanitized_calories, expected_calories),
            ("protein", food.sanitized_protein, expected_protein),
            ("carbs", food.sanitized_carbs, expected_carbs),
            ("fat", food.sanitized_fat, expected_fat),
            ("fiber", food.sanitized_fiber, expected_fiber),
        ]

        for field, actual, expected in checks:
            if _diff_exceeds_tolerance(actual, expected):
                food_failed = True
                reasons.append(
                    f"{field}: sanitized={actual}, expected={expected}"
                )

        if food_failed:
            custom_failures += 1
            failures.append({
                "name": food.name,
                "reason": "; ".join(reasons),
                "food_id": food.id,
                "type": "custom",
            })

    # ---- Incomplete count ----
    incomplete_result = await db.execute(
        select(Food).where(Food.is_complete == False)  # noqa: E712
    )
    incomplete_foods = incomplete_result.scalars().all()
    incomplete_count = len(incomplete_foods)

    return {
        "usda_checked": usda_checked,
        "usda_failures": usda_failures,
        "custom_checked": custom_checked,
        "custom_failures": custom_failures,
        "null_calories_usda": null_calories_usda,
        "incomplete_count": incomplete_count,
        "failures": failures,
    }
