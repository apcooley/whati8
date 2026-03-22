"""Tests for the recipe service layer.

Step 2: CRUD, nutrition calculation, materialization, circular dependency
detection, versioning, and cascade updates.
"""

import pytest
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models import Food, User, FoodPortion
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.nutrient import Nutrient
from whati8.models.recipe import Recipe, RecipeIngredient, RecipeVersion
from whati8.models.user_food import UserFood


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    from whati8.schemas.auth import UserCreate
    from whati8.services.auth import AuthService
    return await AuthService.create_user(db_session, UserCreate(
        username="recipeuser", email="recipe@test.com", password="testpass123",
    ))


@pytest.fixture
async def energy_nutrient(db_session: AsyncSession, seed_test_data) -> Nutrient:
    """Get the Energy nutrient from seed data."""
    result = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Energy"))
    assert result is not None
    return result


@pytest.fixture
async def protein_nutrient(db_session: AsyncSession, seed_test_data) -> Nutrient:
    result = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Protein"))
    assert result is not None
    return result


@pytest.fixture
async def sample_foods(
    db_session: AsyncSession, user: User, energy_nutrient: Nutrient, protein_nutrient: Nutrient
) -> dict[str, Food]:
    """Create sample foods with known nutrition for predictable calculations.
    
    All are custom foods (created_by_user_id set), nutrients per serving_size.
    Energy stored in kcal (matching test seed data).
    """
    foods = {}
    food_data = [
        # name, serving_size, cal_per_serving, protein_per_serving, gram_weight_per_portion
        ("Flour", 100, 364, 10, 100),      # 364 kcal per 100g
        ("Sugar", 100, 387, 0, 100),       # 387 kcal per 100g
        ("Butter", 14, 102, 0.1, 14),      # 102 kcal per 14g (1 tbsp)
        ("Eggs", 50, 72, 6.3, 50),         # 72 kcal per 50g (1 large egg)
    ]
    
    for name, serving_size, cal, protein, portion_g in food_data:
        food = Food(name=name, serving_size=serving_size, unit="g", created_by_user_id=user.id)
        db_session.add(food)
        await db_session.flush()
        
        db_session.add(FoodNutrient(food_id=food.id, nutrient_id=energy_nutrient.id, amount_per_serving=cal))
        db_session.add(FoodNutrient(food_id=food.id, nutrient_id=protein_nutrient.id, amount_per_serving=protein))
        
        # Add a portion
        db_session.add(FoodPortion(
            food_id=food.id, amount=1, unit_name="g",
            gram_weight=1.0, portion_description="grams", sequence_number=1,
        ))
        
        foods[name] = food
    
    await db_session.commit()
    return foods


class TestRecipeCreate:
    """Test creating recipes and materializing as foods."""

    async def test_create_simple_recipe(self, db_session: AsyncSession, user: User, sample_foods):
        """Create a recipe with 2 ingredients, verify it materializes as a food."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session,
            user_id=user.id,
            name="Simple Cake",
            servings=8,
            serving_unit="slice",
            ingredients=[
                {"food_id": sample_foods["Flour"].id, "quantity": 200, "unit": "grams", "portion_description": "grams"},
                {"food_id": sample_foods["Sugar"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        assert recipe.name == "Simple Cake"
        assert float(recipe.servings) == 8.0
        assert recipe.serving_unit == "slice"
        assert recipe.current_version == 1
        assert recipe.current_food_id is not None

    async def test_materialized_food_exists(self, db_session: AsyncSession, user: User, sample_foods):
        """The materialized food should exist in the foods table."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Mat Test",
            servings=4, serving_unit="serving",
            ingredients=[
                {"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        food = await db_session.get(Food, recipe.current_food_id)
        assert food is not None
        assert food.name == "Mat Test"
        assert food.recipe_id == recipe.id
        assert food.recipe_version == 1
        assert food.created_by_user_id == user.id
        assert food.is_recipe_expired is False

    async def test_recipe_version_created(self, db_session: AsyncSession, user: User, sample_foods):
        """A recipe_versions entry should be created."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Version Test",
            servings=1, serving_unit="serving",
            ingredients=[
                {"food_id": sample_foods["Eggs"].id, "quantity": 50, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        result = await db_session.execute(
            select(RecipeVersion).where(RecipeVersion.recipe_id == recipe.id)
        )
        versions = result.scalars().all()
        assert len(versions) == 1
        assert versions[0].version == 1
        assert versions[0].food_id == recipe.current_food_id

    async def test_auto_registered_in_user_foods(self, db_session: AsyncSession, user: User, sample_foods):
        """Recipe should be auto-registered in user_foods."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Auto Reg",
            servings=2, serving_unit="bowl",
            ingredients=[
                {"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        result = await db_session.execute(
            select(UserFood).where(
                UserFood.user_id == user.id,
                UserFood.food_id == recipe.current_food_id,
            )
        )
        uf = result.scalar_one_or_none()
        assert uf is not None
        assert uf.default_quantity == 1


class TestNutritionCalculation:
    """Test per-serving nutrition is calculated correctly."""

    async def test_single_ingredient_nutrition(self, db_session: AsyncSession, user: User, sample_foods):
        """100g flour (364 kcal), 1 serving → 364 kcal per serving."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Just Flour",
            servings=1, serving_unit="serving",
            ingredients=[
                {"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        food = await db_session.get(Food, recipe.current_food_id)
        result = await db_session.execute(
            select(FoodNutrient, Nutrient)
            .join(Nutrient, FoodNutrient.nutrient_id == Nutrient.id)
            .where(FoodNutrient.food_id == food.id, Nutrient.name == "Energy")
        )
        row = result.first()
        assert row is not None
        fn, _ = row
        # Custom food: nutrients stored per serving_size
        # serving_size = total_weight / servings = 100/1 = 100g
        # Energy per serving = 364 kcal (100g flour at 364 kcal/100g)
        assert abs(float(fn.amount_per_serving) - 364) < 1

    async def test_multi_ingredient_nutrition(self, db_session: AsyncSession, user: User, sample_foods):
        """200g flour + 100g sugar, 4 servings → (728+387)/4 = 278.75 kcal/serving."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Flour Sugar Mix",
            servings=4, serving_unit="serving",
            ingredients=[
                {"food_id": sample_foods["Flour"].id, "quantity": 200, "unit": "grams", "portion_description": "grams"},
                {"food_id": sample_foods["Sugar"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        food = await db_session.get(Food, recipe.current_food_id)
        result = await db_session.execute(
            select(FoodNutrient, Nutrient)
            .join(Nutrient, FoodNutrient.nutrient_id == Nutrient.id)
            .where(FoodNutrient.food_id == food.id, Nutrient.name == "Energy")
        )
        fn, _ = result.first()
        # Total: 200g flour * (364/100) + 100g sugar * (387/100) = 728 + 387 = 1115 kcal
        # Per serving: 1115/4 = 278.75
        # But stored per serving_size (= 300/4 = 75g), so amount = 278.75
        assert abs(float(fn.amount_per_serving) - 278.75) < 1

    async def test_serving_size_is_weight_per_serving(self, db_session: AsyncSession, user: User, sample_foods):
        """Materialized food's serving_size = total_weight / servings."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Weight Test",
            servings=4, serving_unit="serving",
            ingredients=[
                {"food_id": sample_foods["Flour"].id, "quantity": 200, "unit": "grams", "portion_description": "grams"},
                {"food_id": sample_foods["Sugar"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        food = await db_session.get(Food, recipe.current_food_id)
        # Total weight: 200 + 100 = 300g, 4 servings → 75g per serving
        assert abs(float(food.serving_size) - 75) < 0.1

    async def test_portions_created(self, db_session: AsyncSession, user: User, sample_foods):
        """Materialized food should have portions: serving unit + grams + oz."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Portion Test",
            servings=2, serving_unit="slice",
            ingredients=[
                {"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        result = await db_session.execute(
            select(FoodPortion).where(FoodPortion.food_id == recipe.current_food_id)
        )
        portions = result.scalars().all()
        unit_names = {p.unit_name for p in portions}
        
        assert "slice" in unit_names, f"Missing serving unit 'slice'. Got: {unit_names}"
        assert "g" in unit_names
        assert "oz" in unit_names


class TestCircularDependency:
    """Test circular dependency detection."""

    async def test_self_reference_rejected(self, db_session: AsyncSession, user: User, sample_foods):
        """Recipe A cannot include its own materialized food."""
        from whati8.services.recipe_service import RecipeService
        
        recipe_a = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Recipe A",
            servings=1, serving_unit="serving",
            ingredients=[
                {"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        with pytest.raises(ValueError, match="[Cc]ircular"):
            await RecipeService.add_ingredient(
                db=db_session, recipe_id=recipe_a.id, user_id=user.id,
                food_id=recipe_a.current_food_id,
                quantity=1, unit="serving", portion_description="serving",
            )

    async def test_mutual_reference_rejected(self, db_session: AsyncSession, user: User, sample_foods):
        """A→B then B→A should be rejected."""
        from whati8.services.recipe_service import RecipeService
        
        recipe_a = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Recipe A",
            servings=1, serving_unit="serving",
            ingredients=[
                {"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"},
            ],
        )
        
        recipe_b = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Recipe B",
            servings=1, serving_unit="serving",
            ingredients=[
                {"food_id": recipe_a.current_food_id, "quantity": 1, "unit": "serving", "portion_description": "serving"},
            ],
        )
        
        with pytest.raises(ValueError, match="[Cc]ircular"):
            await RecipeService.add_ingredient(
                db=db_session, recipe_id=recipe_a.id, user_id=user.id,
                food_id=recipe_b.current_food_id,
                quantity=1, unit="serving", portion_description="serving",
            )

    async def test_transitive_rejected(self, db_session: AsyncSession, user: User, sample_foods):
        """A→B→C, then C→A should be rejected."""
        from whati8.services.recipe_service import RecipeService
        
        recipe_a = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="A",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        )
        recipe_b = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="B",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": recipe_a.current_food_id, "quantity": 1, "unit": "serving", "portion_description": "serving"}],
        )
        recipe_c = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="C",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": recipe_b.current_food_id, "quantity": 1, "unit": "serving", "portion_description": "serving"}],
        )
        
        with pytest.raises(ValueError, match="[Cc]ircular"):
            await RecipeService.add_ingredient(
                db=db_session, recipe_id=recipe_a.id, user_id=user.id,
                food_id=recipe_c.current_food_id,
                quantity=1, unit="serving", portion_description="serving",
            )

    async def test_non_circular_allowed(self, db_session: AsyncSession, user: User, sample_foods):
        """A→B, C→D, adding D to A should be fine (no cycle)."""
        from whati8.services.recipe_service import RecipeService
        
        recipe_a = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="A",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        )
        recipe_b = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="B",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Sugar"].id, "quantity": 50, "unit": "grams", "portion_description": "grams"}],
        )
        # A already has flour; B has sugar. Add B's food to A: no cycle
        await RecipeService.add_ingredient(
            db=db_session, recipe_id=recipe_a.id, user_id=user.id,
            food_id=recipe_b.current_food_id,
            quantity=1, unit="serving", portion_description="serving",
        )
        # Should succeed without error

    async def test_plain_food_always_ok(self, db_session: AsyncSession, user: User, sample_foods):
        """Adding a non-recipe food never triggers circular check."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Plain Food Test",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        )
        # Adding another plain food should always work
        await RecipeService.add_ingredient(
            db=db_session, recipe_id=recipe.id, user_id=user.id,
            food_id=sample_foods["Sugar"].id,
            quantity=50, unit="grams", portion_description="grams",
        )


class TestVersioning:
    """Test recipe versioning on ingredient changes."""

    async def test_add_ingredient_creates_new_version(self, db_session: AsyncSession, user: User, sample_foods):
        """Adding an ingredient should increment version."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Version Inc",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        )
        old_food_id = recipe.current_food_id
        assert recipe.current_version == 1
        
        await RecipeService.add_ingredient(
            db=db_session, recipe_id=recipe.id, user_id=user.id,
            food_id=sample_foods["Sugar"].id,
            quantity=50, unit="grams", portion_description="grams",
        )
        
        await db_session.refresh(recipe)
        assert recipe.current_version == 2
        assert recipe.current_food_id != old_food_id

    async def test_old_version_expired(self, db_session: AsyncSession, user: User, sample_foods):
        """Old food version should be marked expired."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Expire Test",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        )
        old_food_id = recipe.current_food_id
        
        await RecipeService.add_ingredient(
            db=db_session, recipe_id=recipe.id, user_id=user.id,
            food_id=sample_foods["Sugar"].id,
            quantity=50, unit="grams", portion_description="grams",
        )
        
        old_food = await db_session.get(Food, old_food_id)
        assert old_food.is_recipe_expired is True

    async def test_name_change_no_new_version(self, db_session: AsyncSession, user: User, sample_foods):
        """Changing recipe name should NOT create a new version."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Old Name",
            servings=2, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        )
        old_food_id = recipe.current_food_id
        
        await RecipeService.update_metadata(
            db=db_session, recipe_id=recipe.id, user_id=user.id,
            name="New Name",
        )
        
        await db_session.refresh(recipe)
        assert recipe.current_version == 1  # no version bump
        assert recipe.current_food_id == old_food_id  # same food

    async def test_servings_change_no_new_version(self, db_session: AsyncSession, user: User, sample_foods):
        """Changing servings count should NOT create a new version but SHOULD recalculate nutrition."""
        from whati8.services.recipe_service import RecipeService
        
        recipe = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Servings Change",
            servings=4, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Flour"].id, "quantity": 200, "unit": "grams", "portion_description": "grams"}],
        )
        # 200g flour = 728 kcal, 4 servings = 182 kcal/serving
        food = await db_session.get(Food, recipe.current_food_id)
        result = await db_session.execute(
            select(FoodNutrient, Nutrient)
            .join(Nutrient, FoodNutrient.nutrient_id == Nutrient.id)
            .where(FoodNutrient.food_id == food.id, Nutrient.name == "Energy")
        )
        fn_before, _ = result.first()
        cal_before = float(fn_before.amount_per_serving)
        assert abs(cal_before - 182) < 1  # 728/4
        
        await RecipeService.update_metadata(
            db=db_session, recipe_id=recipe.id, user_id=user.id,
            servings=8,
        )
        
        await db_session.refresh(recipe)
        assert recipe.current_version == 1  # no version bump
        
        # Re-fetch nutrition
        result = await db_session.execute(
            select(FoodNutrient, Nutrient)
            .join(Nutrient, FoodNutrient.nutrient_id == Nutrient.id)
            .where(FoodNutrient.food_id == food.id, Nutrient.name == "Energy")
        )
        fn_after, _ = result.first()
        cal_after = float(fn_after.amount_per_serving)
        assert abs(cal_after - 91) < 1  # 728/8


class TestCascade:
    """Test cascading updates through recipe dependencies."""

    async def test_edit_child_cascades_to_parent(self, db_session: AsyncSession, user: User, sample_foods):
        """A uses B as ingredient → edit B → A gets new version."""
        from whati8.services.recipe_service import RecipeService
        
        recipe_b = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Child B",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Flour"].id, "quantity": 100, "unit": "grams", "portion_description": "grams"}],
        )
        
        recipe_a = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Parent A",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": recipe_b.current_food_id, "quantity": 1, "unit": "serving", "portion_description": "serving"}],
        )
        old_a_food = recipe_a.current_food_id
        old_a_version = recipe_a.current_version
        
        # Edit B: add sugar
        await RecipeService.add_ingredient(
            db=db_session, recipe_id=recipe_b.id, user_id=user.id,
            food_id=sample_foods["Sugar"].id,
            quantity=50, unit="grams", portion_description="grams",
        )
        
        await db_session.refresh(recipe_a)
        assert recipe_a.current_version > old_a_version, "Parent should get new version"
        assert recipe_a.current_food_id != old_a_food, "Parent should get new food"

    async def test_deep_cascade(self, db_session: AsyncSession, user: User, sample_foods):
        """A→B→C: edit C → both B and A get new versions."""
        from whati8.services.recipe_service import RecipeService
        
        recipe_c = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Deep C",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": sample_foods["Flour"].id, "quantity": 50, "unit": "grams", "portion_description": "grams"}],
        )
        recipe_b = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Deep B",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": recipe_c.current_food_id, "quantity": 1, "unit": "serving", "portion_description": "serving"}],
        )
        recipe_a = await RecipeService.create_recipe(
            db=db_session, user_id=user.id, name="Deep A",
            servings=1, serving_unit="serving",
            ingredients=[{"food_id": recipe_b.current_food_id, "quantity": 1, "unit": "serving", "portion_description": "serving"}],
        )
        
        old_b_ver = recipe_b.current_version
        old_a_ver = recipe_a.current_version
        
        # Edit C
        await RecipeService.add_ingredient(
            db=db_session, recipe_id=recipe_c.id, user_id=user.id,
            food_id=sample_foods["Sugar"].id,
            quantity=25, unit="grams", portion_description="grams",
        )
        
        await db_session.refresh(recipe_b)
        await db_session.refresh(recipe_a)
        
        assert recipe_b.current_version > old_b_ver, "B should cascade"
        assert recipe_a.current_version > old_a_ver, "A should cascade"
