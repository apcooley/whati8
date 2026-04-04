"""Tests for Phase 1 Step 4: Verification script.

Tests verify_sanitization() which validates all sanitized values against
source food_nutrients data.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models import Food, Nutrient
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.food_portion import FoodPortion
from whati8.models.recipe import Recipe, RecipeIngredient


# ---------- Helpers ----------


async def _create_nutrient(db: AsyncSession, name: str, unit: str = "g") -> Nutrient:
    existing = await db.scalar(select(Nutrient).where(Nutrient.name == name))
    if existing:
        return existing
    n = Nutrient(name=name, unit=unit)
    db.add(n)
    await db.flush()
    return n


async def _ensure_nutrients(db: AsyncSession) -> dict[str, Nutrient]:
    names = {
        "Energy": "kcal",
        "Protein": "g",
        "Carbohydrate, by difference": "g",
        "Total lipid (fat)": "g",
        "Fiber, total dietary": "g",
        "Energy (Atwater General Factors)": "kcal",
    }
    result = {}
    for name, unit in names.items():
        result[name] = await _create_nutrient(db, name, unit)
    return result


async def _create_usda_food(
    db: AsyncSession, name: str, fdc_id: int, macros: dict[str, float],
    nutrients_map: dict[str, Nutrient] | None = None,
) -> Food:
    if nutrients_map is None:
        nutrients_map = await _ensure_nutrients(db)
    food = Food(name=name, serving_size=Decimal("100"), unit="g", usda_fdc_id=fdc_id)
    db.add(food)
    await db.flush()
    nutrient_name_map = {
        "calories": "Energy",
        "protein": "Protein",
        "carbs": "Carbohydrate, by difference",
        "fat": "Total lipid (fat)",
        "fiber": "Fiber, total dietary",
    }
    for key, amount in macros.items():
        n = nutrients_map[nutrient_name_map[key]]
        db.add(FoodNutrient(
            food_id=food.id, nutrient_id=n.id,
            amount_per_serving=Decimal(str(amount)),
        ))
    await db.flush()
    return food


# ---------- Tests ----------


@pytest.mark.asyncio
async def test_verify_all_pass_for_correct_sanitization(
    db_session: AsyncSession, setup_database
):
    """Verification should report 0 failures when sanitization is correct."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods
    from whati8.scripts.verify_sanitization import verify_sanitization

    nutrients = await _ensure_nutrients(db_session)
    await _create_usda_food(db_session, "Chicken", 600001, {
        "calories": 165, "protein": 31, "carbs": 0, "fat": 3.6, "fiber": 0,
    }, nutrients)
    await _create_usda_food(db_session, "Rice", 600002, {
        "calories": 130, "protein": 2.7, "carbs": 28, "fat": 0.3, "fiber": 0.4,
    }, nutrients)

    await sanitize_usda_foods(db_session)
    result = await verify_sanitization(db_session)

    assert result["usda_checked"] >= 2
    assert result["usda_failures"] == 0


@pytest.mark.asyncio
async def test_verify_detects_wrong_calories(
    db_session: AsyncSession, setup_database
):
    """Verification should detect when sanitized_calories doesn't match source."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods
    from whati8.scripts.verify_sanitization import verify_sanitization

    nutrients = await _ensure_nutrients(db_session)
    food = await _create_usda_food(db_session, "Bad Chicken", 600003, {
        "calories": 165, "protein": 31, "carbs": 0, "fat": 3.6, "fiber": 0,
    }, nutrients)

    await sanitize_usda_foods(db_session)

    # Corrupt the sanitized value
    food.sanitized_calories = Decimal("999.99")
    await db_session.flush()

    result = await verify_sanitization(db_session)

    assert result["usda_failures"] > 0
    assert any("Bad Chicken" in f["name"] for f in result["failures"])


@pytest.mark.asyncio
async def test_verify_detects_null_calories_for_usda(
    db_session: AsyncSession, setup_database
):
    """Verification should flag USDA food with NULL sanitized_calories."""
    from whati8.scripts.verify_sanitization import verify_sanitization

    # Create USDA food with no sanitization at all
    food = Food(name="Unsanitized USDA", serving_size=Decimal("100"), unit="g", usda_fdc_id=600004)
    db_session.add(food)
    await db_session.flush()

    result = await verify_sanitization(db_session)

    assert result["null_calories_usda"] > 0


@pytest.mark.asyncio
async def test_verify_reports_incomplete_count(
    db_session: AsyncSession, setup_database
):
    """Verification should report count of is_complete=False foods."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods
    from whati8.scripts.verify_sanitization import verify_sanitization

    nutrients = await _ensure_nutrients(db_session)

    # Food with all macros → complete
    await _create_usda_food(db_session, "Complete Food", 600005, {
        "calories": 100, "protein": 10, "carbs": 15, "fat": 5, "fiber": 2,
    }, nutrients)

    # Food with missing protein → incomplete
    food2 = Food(name="Incomplete Food", serving_size=Decimal("100"), unit="g", usda_fdc_id=600006)
    db_session.add(food2)
    await db_session.flush()
    energy_n = nutrients["Energy"]
    db_session.add(FoodNutrient(
        food_id=food2.id, nutrient_id=energy_n.id, amount_per_serving=Decimal("50"),
    ))
    await db_session.flush()

    await sanitize_usda_foods(db_session)
    result = await verify_sanitization(db_session)

    assert result["incomplete_count"] >= 1


@pytest.mark.asyncio
async def test_verify_custom_foods(
    db_session: AsyncSession, setup_database, test_user
):
    """Verification should also check custom foods."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods
    from whati8.scripts.verify_sanitization import verify_sanitization

    nutrients = await _ensure_nutrients(db_session)
    food = Food(
        name="Custom Yogurt", serving_size=Decimal("170"), unit="g",
        created_by_user_id=test_user.id,
    )
    db_session.add(food)
    await db_session.flush()

    for name, val in [("Energy", 100), ("Protein", 17), ("Carbohydrate, by difference", 6),
                      ("Total lipid (fat)", 0), ("Fiber, total dietary", 0)]:
        db_session.add(FoodNutrient(
            food_id=food.id, nutrient_id=nutrients[name].id,
            amount_per_serving=Decimal(str(val)),
        ))
    await db_session.flush()

    await sanitize_custom_foods(db_session)
    result = await verify_sanitization(db_session)

    assert result["custom_checked"] >= 1
    assert result["custom_failures"] == 0


@pytest.mark.asyncio
async def test_verify_detects_wrong_custom_macros(
    db_session: AsyncSession, setup_database, test_user
):
    """Verification should detect corrupted custom food macros."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods
    from whati8.scripts.verify_sanitization import verify_sanitization

    nutrients = await _ensure_nutrients(db_session)
    food = Food(
        name="Bad Custom", serving_size=Decimal("100"), unit="g",
        created_by_user_id=test_user.id,
    )
    db_session.add(food)
    await db_session.flush()

    for name, val in [("Energy", 200), ("Protein", 20), ("Carbohydrate, by difference", 10),
                      ("Total lipid (fat)", 5), ("Fiber, total dietary", 3)]:
        db_session.add(FoodNutrient(
            food_id=food.id, nutrient_id=nutrients[name].id,
            amount_per_serving=Decimal(str(val)),
        ))
    await db_session.flush()

    await sanitize_custom_foods(db_session)

    # Corrupt protein
    food.sanitized_protein = Decimal("999.00")
    await db_session.flush()

    result = await verify_sanitization(db_session)

    assert result["custom_failures"] > 0
    assert any("Bad Custom" in f["name"] for f in result["failures"])


@pytest.mark.asyncio
async def test_verify_returns_summary_stats(
    db_session: AsyncSession, setup_database
):
    """Verification result should include all expected summary keys."""
    from whati8.scripts.verify_sanitization import verify_sanitization

    result = await verify_sanitization(db_session)

    # Check required keys exist
    assert "usda_checked" in result
    assert "usda_failures" in result
    assert "custom_checked" in result
    assert "custom_failures" in result
    assert "null_calories_usda" in result
    assert "incomplete_count" in result
    assert "failures" in result
    assert isinstance(result["failures"], list)


@pytest.mark.asyncio
async def test_verify_atwater_energy_coalescing(
    db_session: AsyncSession, setup_database
):
    """Verification should accept Atwater energy as the correct calories source."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods
    from whati8.scripts.verify_sanitization import verify_sanitization

    nutrients = await _ensure_nutrients(db_session)
    food = Food(name="Atwater Food", serving_size=Decimal("100"), unit="g", usda_fdc_id=600010)
    db_session.add(food)
    await db_session.flush()

    # Add Atwater General energy + plain energy
    db_session.add(FoodNutrient(
        food_id=food.id, nutrient_id=nutrients["Energy (Atwater General Factors)"].id,
        amount_per_serving=Decimal("148.50"),
    ))
    db_session.add(FoodNutrient(
        food_id=food.id, nutrient_id=nutrients["Energy"].id,
        amount_per_serving=Decimal("150.00"),
    ))
    # Add other macros
    for name, val in [("Protein", 20), ("Carbohydrate, by difference", 10),
                      ("Total lipid (fat)", 5), ("Fiber, total dietary", 1)]:
        db_session.add(FoodNutrient(
            food_id=food.id, nutrient_id=nutrients[name].id,
            amount_per_serving=Decimal(str(val)),
        ))
    await db_session.flush()

    await sanitize_usda_foods(db_session)
    result = await verify_sanitization(db_session)

    # Sanitized calories should be 148.50 (Atwater General), and verification should pass
    assert result["usda_failures"] == 0


@pytest.mark.asyncio
async def test_verify_tolerance(
    db_session: AsyncSession, setup_database
):
    """Values within 0.01 tolerance should pass verification."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods
    from whati8.scripts.verify_sanitization import verify_sanitization

    nutrients = await _ensure_nutrients(db_session)
    food = await _create_usda_food(db_session, "Rounding Food", 600011, {
        "calories": 100, "protein": 10, "carbs": 15, "fat": 5, "fiber": 2,
    }, nutrients)

    await sanitize_usda_foods(db_session)

    # Introduce a tiny rounding diff (within 0.01)
    food.sanitized_calories = Decimal("100.01")
    await db_session.flush()

    result = await verify_sanitization(db_session)

    # Should pass — within tolerance
    assert result["usda_failures"] == 0


@pytest.mark.asyncio
async def test_verify_over_tolerance_fails(
    db_session: AsyncSession, setup_database
):
    """Values exceeding 0.01 tolerance should fail verification."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods
    from whati8.scripts.verify_sanitization import verify_sanitization

    nutrients = await _ensure_nutrients(db_session)
    food = await _create_usda_food(db_session, "Over Tolerance", 600012, {
        "calories": 100, "protein": 10, "carbs": 15, "fat": 5, "fiber": 2,
    }, nutrients)

    await sanitize_usda_foods(db_session)

    # Introduce a diff of 0.02 (exceeds 0.01 tolerance)
    food.sanitized_calories = Decimal("100.02")
    await db_session.flush()

    result = await verify_sanitization(db_session)

    assert result["usda_failures"] > 0


@pytest.mark.asyncio
async def test_verify_detects_none_vs_value_mismatch(
    db_session: AsyncSession, setup_database
):
    """Verification should catch when sanitized is None but source has data."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods
    from whati8.scripts.verify_sanitization import verify_sanitization

    nutrients = await _ensure_nutrients(db_session)
    food = await _create_usda_food(db_session, "Nulled Protein", 600013, {
        "calories": 100, "protein": 20, "carbs": 15, "fat": 5, "fiber": 2,
    }, nutrients)

    await sanitize_usda_foods(db_session)

    # Corrupt: set protein to None even though source has 20g
    food.sanitized_protein = None
    await db_session.flush()

    result = await verify_sanitization(db_session)

    assert result["usda_failures"] > 0
    assert any("Nulled Protein" in f["name"] for f in result["failures"])
