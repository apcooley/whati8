"""Tests for Phase 1 Step 2: Sanitization script — USDA foods.

Tests the sanitize_usda_foods() function that populates tier, data_source,
sanitized_base_grams, and 5 sanitized macro columns for USDA foods.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models import Food, Nutrient
from whati8.models.food_nutrient import FoodNutrient


# ---------- Helpers ----------

async def _create_nutrient(db: AsyncSession, name: str, unit: str = "kcal") -> Nutrient:
    """Create a nutrient if it doesn't exist, return it."""
    existing = await db.scalar(select(Nutrient).where(Nutrient.name == name))
    if existing:
        return existing
    n = Nutrient(name=name, unit=unit)
    db.add(n)
    await db.flush()
    return n


async def _create_usda_food(
    db: AsyncSession,
    name: str,
    fdc_id: int,
    nutrients: dict[str, float],
    serving_size: float = 100.0,
    unit: str = "g",
) -> Food:
    """Create a USDA food with given nutrients. nutrients = {nutrient_name: amount_per_100g}."""
    food = Food(name=name, serving_size=Decimal(str(serving_size)), unit=unit, usda_fdc_id=fdc_id)
    db.add(food)
    await db.flush()

    nutrient_unit_map = {
        "Energy": "kcal",
        "Energy (Atwater General Factors)": "kcal",
        "Energy (Atwater Specific Factors)": "kcal",
        "Protein": "g",
        "Carbohydrate, by difference": "g",
        "Carbohydrate, by summation": "g",
        "Total lipid (fat)": "g",
        "Fiber, total dietary": "g",
    }

    for nutrient_name, amount in nutrients.items():
        n = await _create_nutrient(db, nutrient_name, nutrient_unit_map.get(nutrient_name, "g"))
        fn = FoodNutrient(food_id=food.id, nutrient_id=n.id, amount_per_serving=Decimal(str(amount)))
        db.add(fn)
    await db.flush()
    return food


# ---------- Tests ----------

@pytest.mark.asyncio
async def test_sanitize_sets_tier_zero_for_usda(db_session: AsyncSession, setup_database):
    """USDA foods should get tier=0."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Test Chicken", 100001, {
        "Energy": 165.0, "Protein": 31.0, "Carbohydrate, by difference": 0.0,
        "Total lipid (fat)": 3.6, "Fiber, total dietary": 0.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.tier == 0


@pytest.mark.asyncio
async def test_sanitize_sr_legacy_data_source(db_session: AsyncSession, setup_database):
    """SR Legacy food (FDC < 300K, no Atwater energy) should get data_source='sr_legacy'."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Legacy Chicken", 170001, {
        "Energy": 165.0, "Protein": 31.0, "Carbohydrate, by difference": 0.0,
        "Total lipid (fat)": 3.6, "Fiber, total dietary": 0.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.data_source == "sr_legacy"


@pytest.mark.asyncio
async def test_sanitize_foundation_data_source_by_fdc_id(db_session: AsyncSession, setup_database):
    """Foundation food (FDC >= 300K) should get data_source='foundation'."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Foundation Apple", 1750340, {
        "Energy (Atwater General Factors)": 52.0,
        "Protein": 0.26, "Carbohydrate, by difference": 13.8,
        "Total lipid (fat)": 0.17, "Fiber, total dietary": 2.4,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.data_source == "foundation"


@pytest.mark.asyncio
async def test_sanitize_foundation_data_source_by_atwater(db_session: AsyncSession, setup_database):
    """Food with Atwater energy (even FDC < 300K) should get data_source='foundation'."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Atwater Food", 200001, {
        "Energy (Atwater General Factors)": 100.0,
        "Protein": 10.0, "Carbohydrate, by difference": 15.0,
        "Total lipid (fat)": 2.0, "Fiber, total dietary": 1.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.data_source == "foundation"


@pytest.mark.asyncio
async def test_sanitize_base_grams_always_100(db_session: AsyncSession, setup_database):
    """USDA foods should always get sanitized_base_grams=100, regardless of serving_size."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    # USDA food with serving_size != 100
    food = await _create_usda_food(db_session, "Large Serving", 100002, {
        "Energy": 200.0, "Protein": 20.0, "Carbohydrate, by difference": 10.0,
        "Total lipid (fat)": 5.0, "Fiber, total dietary": 3.0,
    }, serving_size=250.0, unit="undetermined")
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_base_grams == Decimal("100.00")


@pytest.mark.asyncio
async def test_sanitize_energy_prefers_atwater_general(db_session: AsyncSession, setup_database):
    """When both Atwater General and plain Energy exist, pick Atwater General."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Multi Energy", 100003, {
        "Energy": 150.0,
        "Energy (Atwater General Factors)": 148.5,
        "Protein": 20.0, "Carbohydrate, by difference": 10.0,
        "Total lipid (fat)": 5.0, "Fiber, total dietary": 1.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_calories == Decimal("148.50")


@pytest.mark.asyncio
async def test_sanitize_energy_prefers_atwater_specific_over_plain(
    db_session: AsyncSession, setup_database
):
    """When Atwater Specific and plain Energy exist (no General), pick Atwater Specific."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Specific Energy", 100004, {
        "Energy": 200.0,
        "Energy (Atwater Specific Factors)": 195.0,
        "Protein": 25.0, "Carbohydrate, by difference": 10.0,
        "Total lipid (fat)": 8.0, "Fiber, total dietary": 2.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_calories == Decimal("195.00")


@pytest.mark.asyncio
async def test_sanitize_energy_atwater_general_over_specific(
    db_session: AsyncSession, setup_database
):
    """When both Atwater General and Specific exist, pick General (highest priority)."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Both Atwater", 100005, {
        "Energy (Atwater General Factors)": 106.0,
        "Energy (Atwater Specific Factors)": 104.0,
        "Protein": 22.5, "Carbohydrate, by difference": 0.0,
        "Total lipid (fat)": 1.5, "Fiber, total dietary": 0.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_calories == Decimal("106.00")


@pytest.mark.asyncio
async def test_sanitize_energy_falls_back_to_plain(db_session: AsyncSession, setup_database):
    """When only plain Energy exists, use it."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Plain Energy Only", 100006, {
        "Energy": 250.0,
        "Protein": 30.0, "Carbohydrate, by difference": 15.0,
        "Total lipid (fat)": 10.0, "Fiber, total dietary": 3.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_calories == Decimal("250.00")


@pytest.mark.asyncio
async def test_sanitize_carbs_prefers_summation(db_session: AsyncSession, setup_database):
    """When both carb variants exist, pick Carbohydrate by summation."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Carb Variants", 100007, {
        "Energy": 100.0, "Protein": 5.0,
        "Carbohydrate, by difference": 20.0,
        "Carbohydrate, by summation": 18.5,
        "Total lipid (fat)": 2.0, "Fiber, total dietary": 3.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_carbs == Decimal("18.50")


@pytest.mark.asyncio
async def test_sanitize_carbs_falls_back_to_difference(db_session: AsyncSession, setup_database):
    """When only Carbohydrate by difference exists, use it."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Carb Difference Only", 100008, {
        "Energy": 100.0, "Protein": 5.0,
        "Carbohydrate, by difference": 22.0,
        "Total lipid (fat)": 2.0, "Fiber, total dietary": 1.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_carbs == Decimal("22.00")


@pytest.mark.asyncio
async def test_sanitize_direct_copy_protein_fat_fiber(db_session: AsyncSession, setup_database):
    """Protein, fat, and fiber should be direct copies from food_nutrients."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Direct Copy", 100009, {
        "Energy": 165.0, "Protein": 31.02, "Carbohydrate, by difference": 0.0,
        "Total lipid (fat)": 3.57, "Fiber, total dietary": 0.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_protein == Decimal("31.02")
    assert food.sanitized_fat == Decimal("3.57")
    assert food.sanitized_fiber == Decimal("0.00")


@pytest.mark.asyncio
async def test_sanitize_is_complete_when_all_macros_present(
    db_session: AsyncSession, setup_database
):
    """is_complete should be True when cal/protein/carb/fat all present."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Complete Food", 100010, {
        "Energy": 100.0, "Protein": 10.0, "Carbohydrate, by difference": 15.0,
        "Total lipid (fat)": 5.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.is_complete is True


@pytest.mark.asyncio
async def test_sanitize_is_incomplete_when_missing_calories(
    db_session: AsyncSession, setup_database
):
    """is_complete should be False when calories are missing."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "No Calories", 100011, {
        "Protein": 10.0, "Carbohydrate, by difference": 15.0,
        "Total lipid (fat)": 5.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.is_complete is False


@pytest.mark.asyncio
async def test_sanitize_is_incomplete_when_missing_protein(
    db_session: AsyncSession, setup_database
):
    """is_complete should be False when protein is missing."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "No Protein", 100012, {
        "Energy": 100.0, "Carbohydrate, by difference": 15.0,
        "Total lipid (fat)": 5.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.is_complete is False


@pytest.mark.asyncio
async def test_sanitize_is_complete_when_missing_fiber(
    db_session: AsyncSession, setup_database
):
    """is_complete should still be True when only fiber is missing."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "No Fiber", 100013, {
        "Energy": 100.0, "Protein": 10.0, "Carbohydrate, by difference": 15.0,
        "Total lipid (fat)": 5.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.is_complete is True
    assert food.sanitized_fiber is None


@pytest.mark.asyncio
async def test_sanitize_sets_imported_at(db_session: AsyncSession, setup_database):
    """imported_at should be set to a non-null datetime."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Import Time Test", 100014, {
        "Energy": 100.0, "Protein": 10.0, "Carbohydrate, by difference": 15.0,
        "Total lipid (fat)": 5.0, "Fiber, total dietary": 2.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.imported_at is not None


@pytest.mark.asyncio
async def test_sanitize_sets_is_deprecated_false(db_session: AsyncSession, setup_database):
    """is_deprecated should be explicitly set to False for USDA foods."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Not Deprecated", 100015, {
        "Energy": 100.0, "Protein": 10.0, "Carbohydrate, by difference": 15.0,
        "Total lipid (fat)": 5.0, "Fiber, total dietary": 2.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.is_deprecated is False


@pytest.mark.asyncio
async def test_sanitize_idempotent(db_session: AsyncSession, setup_database):
    """Running sanitization twice should produce the same result."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Idempotent Test", 100016, {
        "Energy": 165.0, "Protein": 31.0, "Carbohydrate, by difference": 0.0,
        "Total lipid (fat)": 3.6, "Fiber, total dietary": 0.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    first_cal = food.sanitized_calories

    # Run again
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_calories == first_cal


@pytest.mark.asyncio
async def test_sanitize_skips_non_usda_foods(db_session: AsyncSession, setup_database):
    """Non-USDA foods (no usda_fdc_id) should not be touched by USDA sanitization."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    # Create a custom food (no usda_fdc_id) — leave created_by_user_id=None
    # since we only care that it has no usda_fdc_id
    custom_food = Food(name="Custom Food", serving_size=Decimal("100"), unit="g")
    db_session.add(custom_food)
    await db_session.flush()

    await sanitize_usda_foods(db_session)
    await db_session.refresh(custom_food)

    # Should not have been touched
    assert custom_food.tier is None
    assert custom_food.data_source is None
    assert custom_food.sanitized_calories is None


@pytest.mark.asyncio
async def test_sanitize_multiple_foods(db_session: AsyncSession, setup_database):
    """Sanitization should handle multiple foods in one run."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food1 = await _create_usda_food(db_session, "Food A", 100020, {
        "Energy": 100.0, "Protein": 10.0, "Carbohydrate, by difference": 20.0,
        "Total lipid (fat)": 3.0, "Fiber, total dietary": 2.0,
    })
    food2 = await _create_usda_food(db_session, "Food B", 100021, {
        "Energy (Atwater General Factors)": 200.0, "Protein": 25.0,
        "Carbohydrate, by summation": 10.0,
        "Total lipid (fat)": 8.0, "Fiber, total dietary": 1.0,
    })
    await sanitize_usda_foods(db_session)

    await db_session.refresh(food1)
    await db_session.refresh(food2)

    assert food1.sanitized_calories == Decimal("100.00")
    assert food1.data_source == "sr_legacy"

    assert food2.sanitized_calories == Decimal("200.00")
    assert food2.data_source == "foundation"
    assert food2.sanitized_carbs == Decimal("10.00")


@pytest.mark.asyncio
async def test_sanitize_food_with_zero_macros(db_session: AsyncSession, setup_database):
    """Food with all-zero macros should still be marked complete."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Water", 100022, {
        "Energy": 0.0, "Protein": 0.0, "Carbohydrate, by difference": 0.0,
        "Total lipid (fat)": 0.0, "Fiber, total dietary": 0.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)

    assert food.sanitized_calories == Decimal("0.00")
    assert food.sanitized_protein == Decimal("0.00")
    assert food.is_complete is True


@pytest.mark.asyncio
async def test_sanitize_food_with_only_energy(db_session: AsyncSession, setup_database):
    """Food with only energy (no other macros) should be marked incomplete."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods

    food = await _create_usda_food(db_session, "Energy Only", 100023, {
        "Energy": 50.0,
    })
    await sanitize_usda_foods(db_session)
    await db_session.refresh(food)

    assert food.sanitized_calories == Decimal("50.00")
    assert food.sanitized_protein is None
    assert food.is_complete is False
