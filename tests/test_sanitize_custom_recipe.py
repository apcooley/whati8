"""Tests for Phase 1 Step 3: Sanitization script — custom + recipe foods.

Tests sanitize_custom_foods() and sanitize_recipe_foods() functions.
"""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.models import Food, Nutrient
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.food_portion import FoodPortion
from whati8.models.recipe import Recipe, RecipeIngredient


# ---------- Helpers ----------


async def _create_nutrient(db: AsyncSession, name: str, unit: str = "g") -> Nutrient:
    """Create a nutrient if it doesn't exist, return it."""
    existing = await db.scalar(select(Nutrient).where(Nutrient.name == name))
    if existing:
        return existing
    n = Nutrient(name=name, unit=unit)
    db.add(n)
    await db.flush()
    return n


async def _ensure_nutrients(db: AsyncSession) -> dict[str, Nutrient]:
    """Ensure all 5 core nutrients exist and return a dict by name."""
    names = {
        "Energy": "kcal",
        "Protein": "g",
        "Carbohydrate, by difference": "g",
        "Total lipid (fat)": "g",
        "Fiber, total dietary": "g",
    }
    result = {}
    for name, unit in names.items():
        result[name] = await _create_nutrient(db, name, unit)
    return result


async def _create_custom_food(
    db: AsyncSession,
    user_id: int,
    name: str,
    serving_size: float,
    unit: str,
    macros: dict[str, float],
    portions: list[dict] | None = None,
) -> Food:
    """Create a custom food with nutrients and optional portions."""
    nutrients = await _ensure_nutrients(db)
    food = Food(
        name=name,
        serving_size=Decimal(str(serving_size)),
        unit=unit,
        created_by_user_id=user_id,
    )
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
        n = nutrients[nutrient_name_map[key]]
        fn = FoodNutrient(
            food_id=food.id, nutrient_id=n.id, amount_per_serving=Decimal(str(amount))
        )
        db.add(fn)

    if portions:
        for i, p in enumerate(portions):
            fp = FoodPortion(
                food_id=food.id,
                amount=Decimal(str(p["amount"])),
                unit_name=p["unit_name"],
                gram_weight=Decimal(str(p["gram_weight"])),
                sequence_number=i,
            )
            db.add(fp)

    await db.flush()
    return food


# ===================== Custom Food Tests =====================


@pytest.mark.asyncio
async def test_custom_food_tier_10(db_session: AsyncSession, setup_database, test_user):
    """Custom foods should get tier=10."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Custom Jerky", 28.0, "g",
        {"calories": 90, "protein": 9, "carbs": 12, "fat": 0.5, "fiber": 0},
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    assert food.tier == 10


@pytest.mark.asyncio
async def test_custom_food_data_source(db_session: AsyncSession, setup_database, test_user):
    """Custom foods should get data_source='custom'."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Custom Food", 100.0, "g",
        {"calories": 100, "protein": 10, "carbs": 15, "fat": 5, "fiber": 2},
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    assert food.data_source == "custom"


@pytest.mark.asyncio
async def test_custom_food_gram_unit_base_grams(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food with gram unit should have sanitized_base_grams = serving_size."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Yogurt", 170.0, "g",
        {"calories": 100, "protein": 17, "carbs": 6, "fat": 0, "fiber": 0},
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_base_grams == Decimal("170.00")


@pytest.mark.asyncio
async def test_custom_food_oz_unit_base_grams(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food with oz unit should convert to grams (1 oz = 28.3495g)."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Beef Jerky", 1.0, "oz",
        {"calories": 90, "protein": 9, "carbs": 12, "fat": 0.5, "fiber": 0},
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    # 1.0 * 28.3495 = 28.35 (rounded to 2 decimal places)
    assert food.sanitized_base_grams == Decimal("28.35")


@pytest.mark.asyncio
async def test_custom_food_custom_unit_with_portion(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food with custom unit (bar) should use portion gram_weight."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Built Puff Bar", 44.0, "Bar",
        {"calories": 130, "protein": 18, "carbs": 15, "fat": 4, "fiber": 3},
        portions=[
            {"amount": 1.0, "unit_name": "Bar", "gram_weight": 44.0},
            {"amount": 1.0, "unit_name": "g", "gram_weight": 1.0},
            {"amount": 1.0, "unit_name": "oz", "gram_weight": 28.35},
        ],
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    # 44.0 * (44.0 / 1.0) = 1936? No — gram_weight is for 1 Bar = 44g.
    # sanitized_base_grams = gram_weight * (serving_size / portion.amount)
    # = 44.0 * (44.0 / 1.0) = 1936? That's wrong.
    # Actually: serving_size=44 in unit "Bar". portion says 1 Bar = 44g.
    # So the food's serving is 44 Bars? No — serving_size is the numeric part.
    # The LABEL says "44 Bar" which means serving_size=44, unit=Bar.
    # But the portion says 1 Bar = 44g. So serving_size/portion.amount = 44/1 = 44 bars.
    # That would be 44 * 44g = 1936g. That's clearly wrong.
    #
    # Looking at the actual data: "Built Puff Cookie Dough Chunk Protein Bar"
    # serving_size=44.00, unit=Bar, portion: 1 Bar = 44g
    # This means the LABEL serving is "44 Bar" but it really means "44g = 1 bar"
    # The serving_size IS the gram weight. So sanitized_base_grams = 44g.
    #
    # The correct logic: for custom units, sanitized_base_grams = portion.gram_weight
    # scaled by serving_size / portion.amount. But since serving_size=44 and the food
    # is labeled as "44 Bar" (meaning one bar weighing 44g), and the portion says
    # 1 Bar = 44g, the result should just be 44g.
    #
    # Wait — the serving_size number (44) equals the gram_weight (44). That's how
    # custom foods were entered: serving_size = gram weight of one unit.
    # So: base_grams = gram_weight * (serving_size / portion.amount) = 44 * (44/1) = 1936
    # That's wrong. The real answer is 44g.
    #
    # The correct formula for custom units: look up the portion matching the unit,
    # then base_grams = gram_weight * (serving_size / portion.amount)
    # BUT serving_size IS in the custom unit. So "44 Bar" = 44 bars.
    # That makes no sense for food labels.
    #
    # Actually in the real data, serving_size=44 unit=Bar means "one bar weighing 44g"
    # The number IS the gram weight. So the simplest correct logic:
    # base_grams = portion.gram_weight (for 1 unit) * (serving_size / portion_gram_weight)
    # = 44 * (44/44) = 44g ← NO. That's circular.
    #
    # Simplest: base_grams = serving_size (since the app stores serving_size = gram_weight
    # for custom unit foods). But that's fragile.
    #
    # Correct universal formula:
    # base_grams = (serving_size / portion.amount) * portion.gram_weight
    # = (44 / 1) * 44 = 1936 ← Still wrong!
    #
    # The issue is that serving_size=44 in unit "Bar" means "44g per serving"
    # NOT "44 bars per serving". The serving_size IS the gram weight.
    # This is a data quirk. For custom units, base_grams should just be:
    # portion.gram_weight * serving_size / portion.amount
    # But only if serving_size means "number of units". If serving_size IS grams, just use it.
    #
    # The actual behavior in the real app: serving_size for custom-unit foods IS the gram
    # weight per serving. It's always entered that way from labels.
    # So: sanitized_base_grams = serving_size (the numeric value in grams).
    # And for the portion lookup we only need it to validate/confirm.
    #
    # Let's just test what the code should produce: 44.00 grams.
    assert food.sanitized_base_grams == Decimal("44.00")


@pytest.mark.asyncio
async def test_custom_food_bottle_unit_with_portion(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food with bottle unit should use portion gram_weight."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Protein Shake", 325.0, "bottle",
        {"calories": 140, "protein": 30, "carbs": 7, "fat": 1.5, "fiber": 4},
        portions=[
            {"amount": 1.0, "unit_name": "bottle", "gram_weight": 325.0},
            {"amount": 1.0, "unit_name": "g", "gram_weight": 1.0},
            {"amount": 1.0, "unit_name": "oz", "gram_weight": 28.35},
        ],
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    # 325 bottle, 1 bottle = 325g, so base_grams = 325
    assert food.sanitized_base_grams == Decimal("325.00")


@pytest.mark.asyncio
async def test_custom_food_volume_unit_with_portion(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food with volume unit (cup) should use portion gram_weight."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Kefir", 240.0, "cup",
        {"calories": 110, "protein": 11, "carbs": 12, "fat": 2, "fiber": 3},
        portions=[
            {"amount": 1.0, "unit_name": "cup", "gram_weight": 245.0},
            {"amount": 1.0, "unit_name": "g", "gram_weight": 1.0},
        ],
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    # 240 cup, 1 cup = 245g → base_grams = 245 * (240/1) = way too much
    # Actually: serving_size=240 in "cup" → but that's 240 cups?
    # No — like the "Bar" case, serving_size=240 for cup means "240ml serving"
    # And 1 cup = 245g means density-adjusted grams.
    # The actual gram weight for 240ml: 240/1 * 245 = way too much
    # In reality, the serving_size=240 with unit=cup means "240ml" not "240 cups"
    # This is the same pattern: serving_size IS the gram-equivalent weight.
    # So base_grams = serving_size for volume units? No — 240ml ≠ 240g.
    # 
    # The portion says 1 cup = 245g. serving_size=240 in cups.
    # If this means 240 cups → 240 * 245 = absurd.
    # If serving_size is just the gram weight → 240g.
    #
    # Looking at real data: "Lifeway Kefir 1%, Raspberry" has serving_size=240, unit=cup
    # with portion 1 cup = 245g (densities). The label says "1 cup (240ml)" 
    # and the gram weight per serving is 245g. So serving_size=240 is the ml volume.
    #
    # For volume: base_grams = portion.gram_weight * (serving_size / (portion.amount * unit_ml))
    # where 1 cup = 240ml. So serving_size=240ml / (1 cup * 240ml/cup) = 1 cup.
    # Then base_grams = 1 * 245g = 245g.
    #
    # Actually simpler: portion says 1 cup = 245g.
    # Volume unit conversion: 1 cup = ~240ml. serving_size=240 cup → 240 ml?
    # That's 1 cup = 245g, so 240/240 = 1 cup = 245g.
    #
    # For volume units, convert serving_size to portion units:
    # cups_in_serving = serving_size / standard_volume_ml  (240/240=1 cup for cups)
    # base_grams = cups_in_serving * gram_weight = 1 * 245 = 245
    #
    # But that requires knowing standard_volume_ml per unit. Simpler approach:
    # Since the app already stores serving_size as the numeric value in the unit
    # (240 cup = 240ml, which is 1 cup), and the portion gives us
    # gram_weight for portion.amount of that unit, we do:
    # base_grams = (serving_size / standard_ml_per_unit) * (gram_weight / portion.amount)
    #
    # This is getting complicated. The simplest correct answer for this food:
    # The serving is 1 cup (240ml), which weighs 245g.
    # base_grams = 245.00
    assert food.sanitized_base_grams == Decimal("245.00")


@pytest.mark.asyncio
async def test_custom_food_macros_direct_copy(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food macros should be direct copies from food_nutrients."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Simple Food", 100.0, "g",
        {"calories": 200, "protein": 25, "carbs": 10, "fat": 8, "fiber": 3},
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    assert food.sanitized_calories == Decimal("200.00")
    assert food.sanitized_protein == Decimal("25.00")
    assert food.sanitized_carbs == Decimal("10.00")
    assert food.sanitized_fat == Decimal("8.00")
    assert food.sanitized_fiber == Decimal("3.00")


@pytest.mark.asyncio
async def test_custom_food_is_complete(db_session: AsyncSession, setup_database, test_user):
    """Custom food with all 4 required macros should be is_complete=True."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Complete Custom", 100.0, "g",
        {"calories": 100, "protein": 10, "carbs": 15, "fat": 5, "fiber": 2},
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    assert food.is_complete is True


@pytest.mark.asyncio
async def test_custom_food_skips_recipe_foods(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food sanitization should skip recipe foods."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    # Create a recipe food (has recipe_id set)
    recipe = Recipe(user_id=test_user.id, name="Test Recipe", servings=Decimal("4"))
    db_session.add(recipe)
    await db_session.flush()

    recipe_food = Food(
        name="Recipe Food",
        serving_size=Decimal("100"),
        unit="g",
        created_by_user_id=test_user.id,
        recipe_id=recipe.id,
    )
    db_session.add(recipe_food)
    await db_session.flush()

    await sanitize_custom_foods(db_session)
    await db_session.refresh(recipe_food)

    # Should not have been touched
    assert recipe_food.tier is None
    assert recipe_food.data_source is None


@pytest.mark.asyncio
async def test_custom_food_skips_usda_foods(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food sanitization should not touch USDA foods."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    usda_food = Food(
        name="USDA Food", serving_size=Decimal("100"), unit="g", usda_fdc_id=999999
    )
    db_session.add(usda_food)
    await db_session.flush()

    await sanitize_custom_foods(db_session)
    await db_session.refresh(usda_food)

    assert usda_food.tier is None


@pytest.mark.asyncio
async def test_custom_food_incomplete_missing_protein(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food missing protein should be is_complete=False."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "No Protein Custom", 100.0, "g",
        {"calories": 100, "carbs": 15, "fat": 5, "fiber": 2},
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    assert food.is_complete is False
    assert food.sanitized_protein is None


@pytest.mark.asyncio
async def test_custom_food_volume_no_portion_fallback(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food with volume unit but no matching portion should fall back to serving_size."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Mystery Liquid", 240.0, "cup",
        {"calories": 100, "protein": 5, "carbs": 20, "fat": 1, "fiber": 0},
        # No portions at all
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    # Fallback: base_grams = serving_size
    assert food.sanitized_base_grams == Decimal("240.00")


@pytest.mark.asyncio
async def test_custom_food_lb_unit_base_grams(
    db_session: AsyncSession, setup_database, test_user
):
    """Custom food with lb unit should convert to grams (1 lb = 453.592g)."""
    from whati8.scripts.sanitize_foods import sanitize_custom_foods

    food = await _create_custom_food(
        db_session, test_user.id, "Bulk Chicken", 2.0, "lb",
        {"calories": 800, "protein": 160, "carbs": 0, "fat": 20, "fiber": 0},
    )
    await sanitize_custom_foods(db_session)
    await db_session.refresh(food)
    # 2.0 * 453.592 = 907.184 → rounded to 907.18
    assert food.sanitized_base_grams == Decimal("907.18")


# ===================== Recipe Food Tests =====================


@pytest.mark.asyncio
async def test_recipe_food_tier_20(db_session: AsyncSession, setup_database, test_user):
    """Recipe foods should get tier=20."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods, sanitize_recipe_foods

    nutrients = await _ensure_nutrients(db_session)

    # Create two ingredient foods (USDA, already sanitized)
    chicken = Food(
        name="Chicken", serving_size=Decimal("100"), unit="g", usda_fdc_id=500001
    )
    db_session.add(chicken)
    await db_session.flush()
    for name, val in [("Energy", 165), ("Protein", 31), ("Carbohydrate, by difference", 0),
                      ("Total lipid (fat)", 3.6), ("Fiber, total dietary", 0)]:
        db_session.add(FoodNutrient(food_id=chicken.id, nutrient_id=nutrients[name].id,
                                     amount_per_serving=Decimal(str(val))))
    await db_session.flush()
    await sanitize_usda_foods(db_session)

    # Create recipe
    recipe = Recipe(user_id=test_user.id, name="Chicken Recipe", servings=Decimal("2"))
    db_session.add(recipe)
    await db_session.flush()

    # Create recipe food (materialized)
    recipe_food = Food(
        name="Chicken Recipe",
        serving_size=Decimal("100"),
        unit="g",
        recipe_id=recipe.id,
        created_by_user_id=test_user.id,
    )
    db_session.add(recipe_food)
    await db_session.flush()

    recipe.current_food_id = recipe_food.id

    # Add ingredient
    ri = RecipeIngredient(
        recipe_id=recipe.id, food_id=chicken.id,
        quantity=Decimal("200"), unit="g",
    )
    db_session.add(ri)
    await db_session.flush()

    # Add portion for gram conversion
    fp = FoodPortion(
        food_id=chicken.id, amount=Decimal("1"), unit_name="g",
        gram_weight=Decimal("1"), sequence_number=0,
    )
    db_session.add(fp)
    await db_session.flush()

    await sanitize_recipe_foods(db_session)
    await db_session.refresh(recipe_food)

    assert recipe_food.tier == 20
    assert recipe_food.data_source == "recipe"


@pytest.mark.asyncio
async def test_recipe_food_nutrition_calculation(
    db_session: AsyncSession, setup_database, test_user
):
    """Recipe nutrition should be sum of ingredients divided by servings."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods, sanitize_recipe_foods

    nutrients = await _ensure_nutrients(db_session)

    # Create ingredient: rice (per 100g: 130 cal, 2.7g protein, 28g carb, 0.3g fat, 0.4g fiber)
    rice = Food(name="Rice", serving_size=Decimal("100"), unit="g", usda_fdc_id=500002)
    db_session.add(rice)
    await db_session.flush()
    rice_macros = {"Energy": 130, "Protein": 2.7, "Carbohydrate, by difference": 28,
                   "Total lipid (fat)": 0.3, "Fiber, total dietary": 0.4}
    for name, val in rice_macros.items():
        db_session.add(FoodNutrient(food_id=rice.id, nutrient_id=nutrients[name].id,
                                     amount_per_serving=Decimal(str(val))))
    db_session.add(FoodPortion(food_id=rice.id, amount=Decimal("1"), unit_name="g",
                                gram_weight=Decimal("1"), sequence_number=0))
    await db_session.flush()
    await sanitize_usda_foods(db_session)

    # Create recipe: 300g rice, 2 servings → 150g per serving
    recipe = Recipe(user_id=test_user.id, name="Rice Bowl", servings=Decimal("2"))
    db_session.add(recipe)
    await db_session.flush()

    recipe_food = Food(
        name="Rice Bowl", serving_size=Decimal("150"), unit="g",
        recipe_id=recipe.id, created_by_user_id=test_user.id,
    )
    db_session.add(recipe_food)
    await db_session.flush()
    recipe.current_food_id = recipe_food.id

    ri = RecipeIngredient(
        recipe_id=recipe.id, food_id=rice.id,
        quantity=Decimal("300"), unit="g",
    )
    db_session.add(ri)
    await db_session.flush()

    await sanitize_recipe_foods(db_session)
    await db_session.refresh(recipe_food)

    # 300g rice: 300/100 * 130 = 390 cal total. / 2 servings = 195 per serving.
    assert recipe_food.sanitized_calories == Decimal("195.00")
    # 300g rice: 300/100 * 2.7 = 8.1 protein / 2 = 4.05
    assert recipe_food.sanitized_protein == Decimal("4.05")
    # 300g rice: 300/100 * 28 = 84 carbs / 2 = 42.0
    assert recipe_food.sanitized_carbs == Decimal("42.00")
    # base_grams should equal serving_size
    assert recipe_food.sanitized_base_grams == Decimal("150.00")


@pytest.mark.asyncio
async def test_recipe_food_skips_expired(
    db_session: AsyncSession, setup_database, test_user
):
    """Expired recipe foods should not be sanitized."""
    from whati8.scripts.sanitize_foods import sanitize_recipe_foods

    recipe = Recipe(user_id=test_user.id, name="Old Recipe", servings=Decimal("1"))
    db_session.add(recipe)
    await db_session.flush()

    expired_food = Food(
        name="Old Recipe Food", serving_size=Decimal("100"), unit="g",
        recipe_id=recipe.id, is_recipe_expired=True, created_by_user_id=test_user.id,
    )
    db_session.add(expired_food)
    await db_session.flush()

    await sanitize_recipe_foods(db_session)
    await db_session.refresh(expired_food)

    assert expired_food.tier is None
    assert expired_food.sanitized_calories is None


@pytest.mark.asyncio
async def test_recipe_food_multi_ingredient(
    db_session: AsyncSession, setup_database, test_user
):
    """Recipe with multiple ingredients should sum correctly."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods, sanitize_custom_foods, sanitize_recipe_foods

    nutrients = await _ensure_nutrients(db_session)

    # Ingredient 1: Chicken (USDA) — 165 cal, 31g protein per 100g
    chicken = Food(name="Chicken", serving_size=Decimal("100"), unit="g", usda_fdc_id=500003)
    db_session.add(chicken)
    await db_session.flush()
    for name, val in [("Energy", 165), ("Protein", 31), ("Carbohydrate, by difference", 0),
                      ("Total lipid (fat)", 3.6), ("Fiber, total dietary", 0)]:
        db_session.add(FoodNutrient(food_id=chicken.id, nutrient_id=nutrients[name].id,
                                     amount_per_serving=Decimal(str(val))))
    db_session.add(FoodPortion(food_id=chicken.id, amount=Decimal("1"), unit_name="g",
                                gram_weight=Decimal("1"), sequence_number=0))

    # Ingredient 2: Rice (USDA) — 130 cal, 2.7g protein per 100g
    rice = Food(name="Rice", serving_size=Decimal("100"), unit="g", usda_fdc_id=500004)
    db_session.add(rice)
    await db_session.flush()
    for name, val in [("Energy", 130), ("Protein", 2.7), ("Carbohydrate, by difference", 28),
                      ("Total lipid (fat)", 0.3), ("Fiber, total dietary", 0.4)]:
        db_session.add(FoodNutrient(food_id=rice.id, nutrient_id=nutrients[name].id,
                                     amount_per_serving=Decimal(str(val))))
    db_session.add(FoodPortion(food_id=rice.id, amount=Decimal("1"), unit_name="g",
                                gram_weight=Decimal("1"), sequence_number=0))
    await db_session.flush()

    await sanitize_usda_foods(db_session)

    # Recipe: 200g chicken + 300g rice, 4 servings
    recipe = Recipe(user_id=test_user.id, name="Chicken Rice", servings=Decimal("4"))
    db_session.add(recipe)
    await db_session.flush()

    recipe_food = Food(
        name="Chicken Rice", serving_size=Decimal("125"), unit="g",
        recipe_id=recipe.id, created_by_user_id=test_user.id,
    )
    db_session.add(recipe_food)
    await db_session.flush()
    recipe.current_food_id = recipe_food.id

    db_session.add(RecipeIngredient(recipe_id=recipe.id, food_id=chicken.id,
                                     quantity=Decimal("200"), unit="g"))
    db_session.add(RecipeIngredient(recipe_id=recipe.id, food_id=rice.id,
                                     quantity=Decimal("300"), unit="g"))
    await db_session.flush()

    await sanitize_recipe_foods(db_session)
    await db_session.refresh(recipe_food)

    # Chicken: 200/100 * 165 = 330 cal
    # Rice: 300/100 * 130 = 390 cal
    # Total: 720 cal / 4 servings = 180 cal
    assert recipe_food.sanitized_calories == Decimal("180.00")

    # Protein: (200/100*31) + (300/100*2.7) = 62 + 8.1 = 70.1 / 4 = 17.525
    assert recipe_food.sanitized_protein == Decimal("17.53")  # rounded to 2dp


@pytest.mark.asyncio
async def test_recipe_food_ingredient_with_portion_unit(
    db_session: AsyncSession, setup_database, test_user
):
    """Recipe ingredient with non-gram unit should use portion lookup."""
    from whati8.scripts.sanitize_foods import sanitize_usda_foods, sanitize_recipe_foods

    nutrients = await _ensure_nutrients(db_session)

    # Create ingredient: Cheese, per 100g: 400 cal, 25g protein
    cheese = Food(
        name="Cheese", serving_size=Decimal("100"), unit="g", usda_fdc_id=500010
    )
    db_session.add(cheese)
    await db_session.flush()
    for name, val in [("Energy", 400), ("Protein", 25), ("Carbohydrate, by difference", 1),
                      ("Total lipid (fat)", 33), ("Fiber, total dietary", 0)]:
        db_session.add(FoodNutrient(food_id=cheese.id, nutrient_id=nutrients[name].id,
                                     amount_per_serving=Decimal(str(val))))
    # Add oz portion: 1 oz = 28.35g
    db_session.add(FoodPortion(food_id=cheese.id, amount=Decimal("1"), unit_name="oz",
                                gram_weight=Decimal("28.35"), sequence_number=0))
    db_session.add(FoodPortion(food_id=cheese.id, amount=Decimal("1"), unit_name="g",
                                gram_weight=Decimal("1"), sequence_number=1))
    await db_session.flush()
    await sanitize_usda_foods(db_session)

    # Recipe: 2 oz cheese, 1 serving
    recipe = Recipe(user_id=test_user.id, name="Cheesy", servings=Decimal("1"))
    db_session.add(recipe)
    await db_session.flush()

    recipe_food = Food(
        name="Cheesy", serving_size=Decimal("56.70"), unit="g",
        recipe_id=recipe.id, created_by_user_id=test_user.id,
    )
    db_session.add(recipe_food)
    await db_session.flush()
    recipe.current_food_id = recipe_food.id

    # 2 oz of cheese
    db_session.add(RecipeIngredient(
        recipe_id=recipe.id, food_id=cheese.id, quantity=Decimal("2"), unit="oz",
    ))
    await db_session.flush()

    await sanitize_recipe_foods(db_session)
    await db_session.refresh(recipe_food)

    # 2 oz = 2 * 28.35 = 56.7g of cheese
    # 56.7 / 100 * 400 = 226.8 cal / 1 serving = 226.8
    assert recipe_food.sanitized_calories == Decimal("226.80")
