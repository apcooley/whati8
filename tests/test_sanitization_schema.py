"""Tests for Phase 1 Step 1: Sanitization schema columns on Food model.

Verifies that the Food model has all 11 new columns with correct types,
defaults, and nullability. Also verifies that existing food operations
remain unaffected (backward compatibility).
"""

from decimal import Decimal

import pytest
from sqlalchemy import select, inspect
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models import Food, Nutrient
from whati8.models.food_nutrient import FoodNutrient


# ---------- Column existence tests ----------

@pytest.mark.asyncio
async def test_food_model_has_tier_column(db_session: AsyncSession, setup_database):
    """Food model must have a 'tier' SmallInteger column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "tier")


@pytest.mark.asyncio
async def test_food_model_has_data_source_column(db_session: AsyncSession, setup_database):
    """Food model must have a 'data_source' String(50) column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "data_source")


@pytest.mark.asyncio
async def test_food_model_has_is_deprecated_column(db_session: AsyncSession, setup_database):
    """Food model must have an 'is_deprecated' Boolean column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "is_deprecated")


@pytest.mark.asyncio
async def test_food_model_has_imported_at_column(db_session: AsyncSession, setup_database):
    """Food model must have an 'imported_at' DateTime column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "imported_at")


@pytest.mark.asyncio
async def test_food_model_has_is_complete_column(db_session: AsyncSession, setup_database):
    """Food model must have an 'is_complete' Boolean column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "is_complete")


@pytest.mark.asyncio
async def test_food_model_has_sanitized_base_grams(db_session: AsyncSession, setup_database):
    """Food model must have a 'sanitized_base_grams' Numeric column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "sanitized_base_grams")


@pytest.mark.asyncio
async def test_food_model_has_sanitized_calories(db_session: AsyncSession, setup_database):
    """Food model must have a 'sanitized_calories' Numeric column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "sanitized_calories")


@pytest.mark.asyncio
async def test_food_model_has_sanitized_protein(db_session: AsyncSession, setup_database):
    """Food model must have a 'sanitized_protein' Numeric column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "sanitized_protein")


@pytest.mark.asyncio
async def test_food_model_has_sanitized_carbs(db_session: AsyncSession, setup_database):
    """Food model must have a 'sanitized_carbs' Numeric column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "sanitized_carbs")


@pytest.mark.asyncio
async def test_food_model_has_sanitized_fat(db_session: AsyncSession, setup_database):
    """Food model must have a 'sanitized_fat' Numeric column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "sanitized_fat")


@pytest.mark.asyncio
async def test_food_model_has_sanitized_fiber(db_session: AsyncSession, setup_database):
    """Food model must have a 'sanitized_fiber' Numeric column."""
    food = Food(name="Test", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    assert hasattr(food, "sanitized_fiber")


# ---------- Default value tests ----------

@pytest.mark.asyncio
async def test_is_deprecated_defaults_to_false(db_session: AsyncSession, setup_database):
    """is_deprecated must default to False when not specified."""
    food = Food(name="Test Default", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    await db_session.refresh(food)
    assert food.is_deprecated is False


@pytest.mark.asyncio
async def test_is_complete_defaults_to_true(db_session: AsyncSession, setup_database):
    """is_complete must default to True when not specified."""
    food = Food(name="Test Default", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()
    await db_session.refresh(food)
    assert food.is_complete is True


@pytest.mark.asyncio
async def test_new_columns_nullable_by_default(db_session: AsyncSession, setup_database):
    """All sanitized columns and tier/data_source/imported_at should be nullable."""
    food = Food(name="Test Nullable", serving_size=100, unit="g")
    # Don't set any new columns — they should all accept NULL
    db_session.add(food)
    await db_session.flush()
    await db_session.refresh(food)

    assert food.tier is None
    assert food.data_source is None
    assert food.imported_at is None
    assert food.sanitized_base_grams is None
    assert food.sanitized_calories is None
    assert food.sanitized_protein is None
    assert food.sanitized_carbs is None
    assert food.sanitized_fat is None
    assert food.sanitized_fiber is None


# ---------- Value assignment tests ----------

@pytest.mark.asyncio
async def test_tier_accepts_valid_values(db_session: AsyncSession, setup_database):
    """tier column should accept values 0, 1, 10, 20."""
    for tier_val in [0, 1, 10, 20]:
        food = Food(name=f"Tier {tier_val}", serving_size=100, unit="g", tier=tier_val)
        db_session.add(food)
    await db_session.flush()


@pytest.mark.asyncio
async def test_data_source_accepts_valid_values(db_session: AsyncSession, setup_database):
    """data_source column should accept foundation, sr_legacy, custom, recipe."""
    for ds in ["foundation", "sr_legacy", "custom", "recipe"]:
        food = Food(name=f"DS {ds}", serving_size=100, unit="g", data_source=ds)
        db_session.add(food)
    await db_session.flush()


@pytest.mark.asyncio
async def test_sanitized_values_store_decimals(db_session: AsyncSession, setup_database):
    """Sanitized macro columns should store Decimal values correctly."""
    food = Food(
        name="Decimal Test",
        serving_size=Decimal("100.00"),
        unit="g",
        tier=0,
        data_source="sr_legacy",
        sanitized_base_grams=Decimal("100.00"),
        sanitized_calories=Decimal("165.50"),
        sanitized_protein=Decimal("31.02"),
        sanitized_carbs=Decimal("0.00"),
        sanitized_fat=Decimal("3.57"),
        sanitized_fiber=Decimal("0.00"),
        is_complete=True,
    )
    db_session.add(food)
    await db_session.flush()
    await db_session.refresh(food)

    assert food.sanitized_calories == Decimal("165.50")
    assert food.sanitized_protein == Decimal("31.02")
    assert food.sanitized_carbs == Decimal("0.00")
    assert food.sanitized_fat == Decimal("3.57")
    assert food.sanitized_fiber == Decimal("0.00")
    assert food.sanitized_base_grams == Decimal("100.00")


@pytest.mark.asyncio
async def test_imported_at_accepts_datetime(db_session: AsyncSession, setup_database):
    """imported_at should accept a datetime value."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    food = Food(name="Import Time Test", serving_size=100, unit="g", imported_at=now)
    db_session.add(food)
    await db_session.flush()
    await db_session.refresh(food)
    assert food.imported_at is not None


# ---------- Backward compatibility tests ----------

@pytest.mark.asyncio
async def test_existing_food_creation_still_works(db_session: AsyncSession, setup_database):
    """Creating a food without new columns should work (backward compat)."""
    food = Food(
        name="Old-style food",
        serving_size=Decimal("100.00"),
        unit="g",
        usda_fdc_id=999999,
    )
    db_session.add(food)
    await db_session.flush()
    await db_session.refresh(food)

    assert food.id is not None
    assert food.name == "Old-style food"
    assert food.usda_fdc_id == 999999


@pytest.mark.asyncio
async def test_existing_food_with_nutrients_still_works(
    db_session: AsyncSession, setup_database
):
    """Creating food + nutrients without new columns should work."""
    # Create nutrient
    nutrient = Nutrient(name="Test Energy", unit="kcal")
    db_session.add(nutrient)
    await db_session.flush()

    # Create food (no new columns)
    food = Food(name="Classic food", serving_size=100, unit="g")
    db_session.add(food)
    await db_session.flush()

    # Link nutrient
    fn = FoodNutrient(
        food_id=food.id,
        nutrient_id=nutrient.id,
        amount_per_serving=Decimal("200.00"),
    )
    db_session.add(fn)
    await db_session.flush()

    # Query back with eager load
    from sqlalchemy.orm import selectinload

    result = await db_session.scalar(
        select(Food).where(Food.id == food.id).options(selectinload(Food.food_nutrients))
    )
    assert result is not None
    assert len(result.food_nutrients) == 1
    assert result.food_nutrients[0].amount_per_serving == Decimal("200.00")


@pytest.mark.asyncio
async def test_food_repr_still_works(db_session: AsyncSession, setup_database):
    """Food __repr__ shouldn't break with new columns."""
    food = Food(
        name="Repr Test",
        serving_size=100,
        unit="g",
        tier=0,
        sanitized_calories=Decimal("150.00"),
    )
    db_session.add(food)
    await db_session.flush()
    repr_str = repr(food)
    assert "Repr Test" in repr_str


# ---------- Index existence tests ----------

@pytest.mark.asyncio
async def test_tier_index_exists(test_engine, setup_database):
    """Index ix_foods_tier should exist on foods table."""
    async with test_engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_indexes("foods")
        )
    index_names = {idx["name"] for idx in indexes}
    assert "ix_foods_tier" in index_names


@pytest.mark.asyncio
async def test_data_source_index_exists(test_engine, setup_database):
    """Index ix_foods_data_source should exist on foods table."""
    async with test_engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_indexes("foods")
        )
    index_names = {idx["name"] for idx in indexes}
    assert "ix_foods_data_source" in index_names


# ---------- Query tests with new columns ----------

@pytest.mark.asyncio
async def test_filter_by_tier(db_session: AsyncSession, setup_database):
    """Should be able to filter foods by tier."""
    food1 = Food(name="USDA Food", serving_size=100, unit="g", tier=0)
    food2 = Food(name="Custom Food", serving_size=100, unit="g", tier=10)
    food3 = Food(name="Recipe Food", serving_size=100, unit="g", tier=20)
    db_session.add_all([food1, food2, food3])
    await db_session.flush()

    usda_foods = (
        await db_session.scalars(select(Food).where(Food.tier == 0))
    ).all()
    assert any(f.name == "USDA Food" for f in usda_foods)

    custom_foods = (
        await db_session.scalars(select(Food).where(Food.tier == 10))
    ).all()
    assert any(f.name == "Custom Food" for f in custom_foods)


@pytest.mark.asyncio
async def test_filter_by_data_source(db_session: AsyncSession, setup_database):
    """Should be able to filter foods by data_source."""
    food1 = Food(
        name="Foundation Food", serving_size=100, unit="g", data_source="foundation"
    )
    food2 = Food(
        name="Legacy Food", serving_size=100, unit="g", data_source="sr_legacy"
    )
    db_session.add_all([food1, food2])
    await db_session.flush()

    foundation_foods = (
        await db_session.scalars(
            select(Food).where(Food.data_source == "foundation")
        )
    ).all()
    assert any(f.name == "Foundation Food" for f in foundation_foods)


@pytest.mark.asyncio
async def test_filter_by_is_complete(db_session: AsyncSession, setup_database):
    """Should be able to filter foods by is_complete."""
    food1 = Food(name="Complete Food", serving_size=100, unit="g", is_complete=True)
    food2 = Food(name="Incomplete Food", serving_size=100, unit="g", is_complete=False)
    db_session.add_all([food1, food2])
    await db_session.flush()

    complete = (
        await db_session.scalars(select(Food).where(Food.is_complete == True))
    ).all()
    assert any(f.name == "Complete Food" for f in complete)

    incomplete = (
        await db_session.scalars(select(Food).where(Food.is_complete == False))
    ).all()
    assert any(f.name == "Incomplete Food" for f in incomplete)
