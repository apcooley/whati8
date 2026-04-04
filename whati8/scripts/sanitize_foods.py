"""
Sanitization script for USDA food data.

Populates tier, data_source, sanitized_base_grams, and sanitized macro columns
for all USDA foods (those with usda_fdc_id set).
"""

import re
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.models.food import Food
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.recipe import Recipe, RecipeIngredient


ENERGY_ATWATER_GENERAL = "Energy (Atwater General Factors)"
ENERGY_ATWATER_SPECIFIC = "Energy (Atwater Specific Factors)"
ENERGY_PLAIN = "Energy"

CARB_SUMMATION = "Carbohydrate, by summation"
CARB_DIFFERENCE = "Carbohydrate, by difference"

PROTEIN = "Protein"
FAT = "Total lipid (fat)"
FIBER = "Fiber, total dietary"

FOUNDATION_FDC_THRESHOLD = 300_000


async def sanitize_usda_foods(db: AsyncSession) -> dict:
    """
    Sanitize all USDA foods (where usda_fdc_id IS NOT NULL).

    Sets tier, data_source, sanitized_base_grams, sanitized_calories,
    sanitized_protein, sanitized_carbs, sanitized_fat, sanitized_fiber,
    is_complete, imported_at, and is_deprecated.

    Returns a stats dict with counts.
    """
    result = await db.execute(
        select(Food)
        .where(Food.usda_fdc_id.is_not(None))
        .options(
            selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient)
        )
    )
    foods = result.scalars().all()

    processed = 0
    complete = 0
    incomplete = 0

    for food in foods:
        # Build a map of nutrient name → amount
        nutrient_map: dict[str, Decimal] = {}
        for fn in food.food_nutrients:
            if fn.nutrient:
                nutrient_map[fn.nutrient.name] = fn.amount_per_serving

        # Tier
        food.tier = 0

        # Data source
        has_atwater = (
            ENERGY_ATWATER_GENERAL in nutrient_map
            or ENERGY_ATWATER_SPECIFIC in nutrient_map
        )
        if food.usda_fdc_id >= FOUNDATION_FDC_THRESHOLD or has_atwater:
            food.data_source = "foundation"
        else:
            food.data_source = "sr_legacy"

        # Base grams (always 100 for USDA)
        food.sanitized_base_grams = Decimal("100.00")

        # Energy coalescing
        if ENERGY_ATWATER_GENERAL in nutrient_map:
            food.sanitized_calories = nutrient_map[ENERGY_ATWATER_GENERAL]
        elif ENERGY_ATWATER_SPECIFIC in nutrient_map:
            food.sanitized_calories = nutrient_map[ENERGY_ATWATER_SPECIFIC]
        elif ENERGY_PLAIN in nutrient_map:
            food.sanitized_calories = nutrient_map[ENERGY_PLAIN]
        else:
            food.sanitized_calories = None

        # Carbohydrate coalescing
        if CARB_SUMMATION in nutrient_map:
            food.sanitized_carbs = nutrient_map[CARB_SUMMATION]
        elif CARB_DIFFERENCE in nutrient_map:
            food.sanitized_carbs = nutrient_map[CARB_DIFFERENCE]
        else:
            food.sanitized_carbs = None

        # Direct copies
        food.sanitized_protein = nutrient_map.get(PROTEIN)
        food.sanitized_fat = nutrient_map.get(FAT)
        food.sanitized_fiber = nutrient_map.get(FIBER)

        # Completeness check (fiber is optional)
        if any(
            v is None
            for v in [
                food.sanitized_calories,
                food.sanitized_protein,
                food.sanitized_carbs,
                food.sanitized_fat,
            ]
        ):
            food.is_complete = False
            incomplete += 1
        else:
            food.is_complete = True
            complete += 1

        # Timestamps and flags
        food.imported_at = datetime.now(UTC)
        food.is_deprecated = False

        processed += 1

    # Flush all changes to the DB within the current transaction
    await db.flush()

    return {
        "processed": processed,
        "complete": complete,
        "incomplete": incomplete,
    }


# Gram conversions for mass units
_MASS_CONVERSIONS: dict[str, float] = {
    "oz": 28.3495,
    "lb": 453.592,
    "kg": 1000.0,
}

# Standard millilitres per volume unit (for serving_size stored as ml)
_VOLUME_ML: dict[str, float] = {
    "cup": 240.0,
    "tbsp": 15.0,
    "tsp": 5.0,
    "ml": 1.0,
    "fl oz": 29.5735,
}

# Gram units (serving_size is already in grams)
_GRAM_UNITS = {"g", "gram", "grams"}


def _extract_grams_from_unit(unit: str) -> float | None:
    """Try to parse 'small (70.0g)' or '1.0 cup (220.0g)' patterns."""
    match = re.search(r"\((\d+(\.\d+)?)\s*g\)", unit.lower())
    if match:
        return float(match.group(1))
    return None


async def sanitize_custom_foods(db: AsyncSession) -> dict:
    """
    Sanitize all custom foods (created_by_user_id IS NOT NULL, recipe_id IS NULL,
    usda_fdc_id IS NULL).

    Returns a stats dict with counts.
    """
    result = await db.execute(
        select(Food)
        .where(
            Food.created_by_user_id.is_not(None),
            Food.recipe_id.is_(None),
            Food.usda_fdc_id.is_(None),
        )
        .options(
            selectinload(Food.food_nutrients).selectinload(FoodNutrient.nutrient),
            selectinload(Food.portions),
        )
    )
    foods = result.scalars().all()

    processed = 0
    complete = 0
    incomplete = 0

    for food in foods:
        # Nutrient map
        nutrient_map: dict[str, Decimal] = {}
        for fn in food.food_nutrients:
            if fn.nutrient:
                nutrient_map[fn.nutrient.name] = fn.amount_per_serving

        food.tier = 10
        food.data_source = "custom"

        # Determine sanitized_base_grams based on unit
        unit_lower = (food.unit or "").lower().strip()
        serving = float(food.serving_size)

        if unit_lower in _GRAM_UNITS:
            food.sanitized_base_grams = round(Decimal(str(serving)), 2)
        elif unit_lower in _MASS_CONVERSIONS:
            food.sanitized_base_grams = round(
                Decimal(str(serving * _MASS_CONVERSIONS[unit_lower])), 2
            )
        elif unit_lower in _VOLUME_ML:
            # serving_size stored as ml equivalent; convert to portion units then to grams
            std_ml = _VOLUME_ML[unit_lower]
            portion = next(
                (p for p in food.portions if p.unit_name.lower() == unit_lower), None
            )
            if portion:
                units_count = serving / std_ml
                base_grams = units_count * float(portion.gram_weight) / float(portion.amount)
                food.sanitized_base_grams = round(Decimal(str(base_grams)), 2)
            else:
                # Fallback: assume 1:1 with ml
                food.sanitized_base_grams = round(Decimal(str(serving)), 2)
        else:
            # Custom unit (bar, bottle, slice, etc.) — serving_size IS the gram weight
            food.sanitized_base_grams = round(Decimal(str(serving)), 2)

        # Copy macros directly from food_nutrients
        food.sanitized_calories = nutrient_map.get(ENERGY_PLAIN)
        food.sanitized_protein = nutrient_map.get(PROTEIN)
        food.sanitized_carbs = nutrient_map.get(CARB_DIFFERENCE)
        food.sanitized_fat = nutrient_map.get(FAT)
        food.sanitized_fiber = nutrient_map.get(FIBER)

        # Completeness
        if any(
            v is None
            for v in [
                food.sanitized_calories,
                food.sanitized_protein,
                food.sanitized_carbs,
                food.sanitized_fat,
            ]
        ):
            food.is_complete = False
            incomplete += 1
        else:
            food.is_complete = True
            complete += 1

        food.imported_at = datetime.now(UTC)
        food.is_deprecated = False
        processed += 1

    await db.flush()

    return {
        "processed": processed,
        "complete": complete,
        "incomplete": incomplete,
    }


async def sanitize_recipe_foods(db: AsyncSession) -> dict:
    """
    Sanitize all recipe foods by computing nutrition from ingredients.

    Depends on USDA and custom foods already having sanitized_* values.
    Returns a stats dict with counts.
    """
    result = await db.execute(
        select(Recipe)
        .options(
            selectinload(Recipe.ingredients)
            .selectinload(RecipeIngredient.food)
            .selectinload(Food.portions),
            selectinload(Recipe.current_food),
        )
    )
    recipes = result.scalars().all()

    processed = 0
    complete = 0
    incomplete = 0

    for recipe in recipes:
        # Skip recipes without a materialised food
        if not recipe.current_food_id or not recipe.current_food:
            continue

        food = recipe.current_food

        # Skip expired recipe foods
        if food.is_recipe_expired:
            continue

        food.tier = 20
        food.data_source = "recipe"
        food.sanitized_base_grams = round(Decimal(str(float(food.serving_size))), 2)

        # Sum macros from ingredients
        total_cal = Decimal("0")
        total_prot = Decimal("0")
        total_carb = Decimal("0")
        total_fat = Decimal("0")
        total_fiber = Decimal("0")

        for ing in recipe.ingredients:
            ing_food = ing.food
            if not ing_food or not ing_food.sanitized_base_grams:
                continue

            # Convert ingredient quantity to grams
            ing_unit = (ing.unit or "").lower().strip()
            qty = float(ing.quantity)

            grams = None
            if ing_unit in _GRAM_UNITS or ing_unit == "g":
                grams = qty
            else:
                # Try to extract weight from unit string like "small (70.0g)"
                extracted_base = _extract_grams_from_unit(ing_unit)
                if extracted_base is not None:
                    grams = qty * extracted_base
                else:
                    # Look up portion matching unit
                    portion = next(
                        (
                            p
                            for p in ing_food.portions
                            if p.unit_name.lower() == ing_unit
                        ),
                        None,
                    )
                    if portion:
                        grams = qty / float(portion.amount) * float(portion.gram_weight)
                    elif ing_unit in _VOLUME_ML:
                        # Fallback for volume units if portion is missing
                        grams = qty * _VOLUME_ML[ing_unit]
                    elif ing_unit in _MASS_CONVERSIONS:
                        # Fallback for mass units if portion is missing
                        grams = qty * _MASS_CONVERSIONS[ing_unit]

            if grams is None:
                # Unknown unit — skip
                continue

            base = float(ing_food.sanitized_base_grams)
            if base == 0:
                continue
            scale = grams / base

            if ing_food.sanitized_calories is not None:
                total_cal += Decimal(str(scale * float(ing_food.sanitized_calories)))
            if ing_food.sanitized_protein is not None:
                total_prot += Decimal(str(scale * float(ing_food.sanitized_protein)))
            if ing_food.sanitized_carbs is not None:
                total_carb += Decimal(str(scale * float(ing_food.sanitized_carbs)))
            if ing_food.sanitized_fat is not None:
                total_fat += Decimal(str(scale * float(ing_food.sanitized_fat)))
            if ing_food.sanitized_fiber is not None:
                total_fiber += Decimal(str(scale * float(ing_food.sanitized_fiber)))

        # Divide by servings
        servings = Decimal(str(float(recipe.servings)))
        if servings > 0:
            food.sanitized_calories = round(total_cal / servings, 2)
            food.sanitized_protein = round(total_prot / servings, 2)
            food.sanitized_carbs = round(total_carb / servings, 2)
            food.sanitized_fat = round(total_fat / servings, 2)
            food.sanitized_fiber = round(total_fiber / servings, 2)
        else:
            food.sanitized_calories = None
            food.sanitized_protein = None
            food.sanitized_carbs = None
            food.sanitized_fat = None
            food.sanitized_fiber = None

        # Completeness
        if any(
            v is None
            for v in [
                food.sanitized_calories,
                food.sanitized_protein,
                food.sanitized_carbs,
                food.sanitized_fat,
            ]
        ):
            food.is_complete = False
            incomplete += 1
        else:
            food.is_complete = True
            complete += 1

        food.imported_at = datetime.now(UTC)
        food.is_deprecated = False
        processed += 1

    await db.flush()

    return {
        "processed": processed,
        "complete": complete,
        "incomplete": incomplete,
    }
