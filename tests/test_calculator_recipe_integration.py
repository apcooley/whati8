"""Integration tests for NutrientCalculator in recipe materialization context.

Step 4: Verify recipe_service uses NutrientCalculator instead of inline coalescing.
The key difference: recipe materialization needs per-nutrient-id totals (to create
FoodNutrient records), not friendly-name summaries.
"""
import pytest
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from whati8.models.food import Food
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.nutrient import Nutrient
from whati8.models.recipe import Recipe
from whati8.models.user import User
from whati8.services.recipe_service import RecipeService


@pytest.fixture
async def energy_nutrients(db_session):
    """Create plain Energy + Atwater General energy nutrients."""
    plain = Nutrient(name="Energy", unit="kcal")
    atwater = Nutrient(name="Energy (Atwater General Factors)", unit="kcal")
    db_session.add_all([plain, atwater])
    await db_session.flush()
    return {"plain": plain, "atwater": atwater}


@pytest.fixture
async def carb_nutrients(db_session):
    """Create both carb variants."""
    by_diff = Nutrient(name="Carbohydrate, by difference", unit="g")
    by_sum = Nutrient(name="Carbohydrate, by summation", unit="g")
    db_session.add_all([by_diff, by_sum])
    await db_session.flush()
    return {"by_diff": by_diff, "by_sum": by_sum}


@pytest.fixture
async def protein_nutrient(db_session):
    protein = Nutrient(name="Protein", unit="g")
    db_session.add(protein)
    await db_session.flush()
    return protein


@pytest.fixture
async def recipe_user(db_session):
    """Create a test user for recipe tests."""
    user = User(username="recipe_calc_test", email="recipe_calc@test.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def mixed_energy_foods(db_session, recipe_user, energy_nutrients, carb_nutrients, protein_nutrient):
    """Create two foods: one USDA with Atwater energy, one custom with plain energy.

    USDA food (per 100g): 200 kcal (Atwater), 150 kcal (plain), 10g protein, 25g carbs (by diff), 20g carbs (by sum)
    Custom food (per 50g serving): 100 kcal (plain only), 15g protein, 12g carbs (by diff only)

    Recipe: 200g USDA + 2 servings custom = 400 kcal (Atwater) + 200 kcal (plain) = 600 kcal total
    """
    # USDA food (per 100g base)
    usda_food = Food(name="USDA Mixed Energy Food", serving_size=100, unit="g", created_by_user_id=None)
    db_session.add(usda_food)
    await db_session.flush()

    # USDA nutrients
    db_session.add_all([
        FoodNutrient(food_id=usda_food.id, nutrient_id=energy_nutrients["atwater"].id, amount_per_serving=Decimal("200")),
        FoodNutrient(food_id=usda_food.id, nutrient_id=energy_nutrients["plain"].id, amount_per_serving=Decimal("150")),
        FoodNutrient(food_id=usda_food.id, nutrient_id=protein_nutrient.id, amount_per_serving=Decimal("10")),
        FoodNutrient(food_id=usda_food.id, nutrient_id=carb_nutrients["by_diff"].id, amount_per_serving=Decimal("25")),
        FoodNutrient(food_id=usda_food.id, nutrient_id=carb_nutrients["by_sum"].id, amount_per_serving=Decimal("20")),
    ])

    # Custom food (per 50g serving)
    custom_food = Food(name="Custom Plain Energy Food", serving_size=50, unit="g", created_by_user_id=recipe_user.id)
    db_session.add(custom_food)
    await db_session.flush()

    db_session.add_all([
        FoodNutrient(food_id=custom_food.id, nutrient_id=energy_nutrients["plain"].id, amount_per_serving=Decimal("100")),
        FoodNutrient(food_id=custom_food.id, nutrient_id=protein_nutrient.id, amount_per_serving=Decimal("15")),
        FoodNutrient(food_id=custom_food.id, nutrient_id=carb_nutrients["by_diff"].id, amount_per_serving=Decimal("12")),
    ])
    await db_session.flush()

    return {"usda": usda_food, "custom": custom_food}


class TestRecipeMaterializationCoalescing:
    """Verify recipe materialization correctly coalesces energy/carbs via NutrientCalculator."""

    @pytest.mark.asyncio
    async def test_recipe_coalesces_energy_from_mixed_foods(
        self, db_session, recipe_user, mixed_energy_foods, energy_nutrients
    ):
        """Recipe with USDA (Atwater) + custom (plain) food should coalesce energy correctly.

        USDA: 200g × (200 kcal/100g) = 400 kcal (Atwater wins over plain 150)
        Custom: 100g × (100 kcal/50g) = 200 kcal (plain, only option)
        Total: 600 kcal, stored under canonical Energy nutrient
        Per serving (2 servings): 300 kcal
        """
        recipe = Recipe(
            name="Mixed Energy Recipe",
            user_id=recipe_user.id,
            servings=Decimal("2"),
        )
        db_session.add(recipe)
        await db_session.flush()

        from whati8.models.recipe import RecipeIngredient
        db_session.add_all([
            RecipeIngredient(recipe_id=recipe.id, food_id=mixed_energy_foods["usda"].id,
                           quantity=Decimal("200"), unit="g"),
            RecipeIngredient(recipe_id=recipe.id, food_id=mixed_energy_foods["custom"].id,
                           quantity=Decimal("100"), unit="g"),
        ])
        await db_session.flush()

        food = await RecipeService._materialize_recipe(db_session, recipe, recipe_user.id, 1)

        # Load the materialized food's nutrients
        result = await db_session.execute(
            select(FoodNutrient)
            .where(FoodNutrient.food_id == food.id)
            .options(selectinload(FoodNutrient.nutrient))
        )
        food_nutrients = result.scalars().all()

        # Find energy nutrient(s)
        energy_fns = [fn for fn in food_nutrients if "energy" in fn.nutrient.name.lower() or "atwater" in fn.nutrient.name.lower()]

        # Should have exactly 1 coalesced energy value (not multiple variants)
        assert len(energy_fns) == 1, f"Expected 1 energy nutrient, got {len(energy_fns)}: {[fn.nutrient.name for fn in energy_fns]}"

        # Per serving: (400 + 200) / 2 = 300 kcal
        energy_val = float(energy_fns[0].amount_per_serving)
        assert abs(energy_val - 300) < 1, f"Expected ~300 kcal/serving, got {energy_val}"

    @pytest.mark.asyncio
    async def test_recipe_coalesces_carbs_from_mixed_foods(
        self, db_session, recipe_user, mixed_energy_foods, carb_nutrients
    ):
        """Recipe should coalesce carbs: by_sum preferred for USDA, by_diff for custom.

        USDA: 200g × (20g/100g) = 40g carbs (by summation wins)
        Custom: 100g × (12g/50g) = 24g carbs (by diff, only option)
        Total: 64g, per serving (2): 32g
        """
        recipe = Recipe(
            name="Mixed Carb Recipe",
            user_id=recipe_user.id,
            servings=Decimal("2"),
        )
        db_session.add(recipe)
        await db_session.flush()

        from whati8.models.recipe import RecipeIngredient
        db_session.add_all([
            RecipeIngredient(recipe_id=recipe.id, food_id=mixed_energy_foods["usda"].id,
                           quantity=Decimal("200"), unit="g"),
            RecipeIngredient(recipe_id=recipe.id, food_id=mixed_energy_foods["custom"].id,
                           quantity=Decimal("100"), unit="g"),
        ])
        await db_session.flush()

        food = await RecipeService._materialize_recipe(db_session, recipe, recipe_user.id, 1)

        result = await db_session.execute(
            select(FoodNutrient)
            .where(FoodNutrient.food_id == food.id)
            .options(selectinload(FoodNutrient.nutrient))
        )
        food_nutrients = result.scalars().all()

        carb_fns = [fn for fn in food_nutrients if "carbohydrate" in fn.nutrient.name.lower()]
        assert len(carb_fns) == 1, f"Expected 1 carb nutrient, got {len(carb_fns)}: {[fn.nutrient.name for fn in carb_fns]}"

        carb_val = float(carb_fns[0].amount_per_serving)
        assert abs(carb_val - 32) < 1, f"Expected ~32g carbs/serving, got {carb_val}"

    @pytest.mark.asyncio
    async def test_recipe_protein_not_affected_by_coalescing(
        self, db_session, recipe_user, mixed_energy_foods, protein_nutrient
    ):
        """Protein should sum normally (no coalescing needed).

        USDA: 200g × (10g/100g) = 20g
        Custom: 100g × (15g/50g) = 30g
        Total: 50g, per serving (2): 25g
        """
        recipe = Recipe(
            name="Protein Recipe",
            user_id=recipe_user.id,
            servings=Decimal("2"),
        )
        db_session.add(recipe)
        await db_session.flush()

        from whati8.models.recipe import RecipeIngredient
        db_session.add_all([
            RecipeIngredient(recipe_id=recipe.id, food_id=mixed_energy_foods["usda"].id,
                           quantity=Decimal("200"), unit="g"),
            RecipeIngredient(recipe_id=recipe.id, food_id=mixed_energy_foods["custom"].id,
                           quantity=Decimal("100"), unit="g"),
        ])
        await db_session.flush()

        food = await RecipeService._materialize_recipe(db_session, recipe, recipe_user.id, 1)

        result = await db_session.execute(
            select(FoodNutrient)
            .where(FoodNutrient.food_id == food.id)
            .options(selectinload(FoodNutrient.nutrient))
        )
        food_nutrients = result.scalars().all()

        protein_fns = [fn for fn in food_nutrients if fn.nutrient.name == "Protein"]
        assert len(protein_fns) == 1
        protein_val = float(protein_fns[0].amount_per_serving)
        assert abs(protein_val - 25) < 1, f"Expected ~25g protein/serving, got {protein_val}"
