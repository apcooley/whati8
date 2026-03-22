"""Tests for recipe data model and schema changes.

Step 1: Verify the DB schema supports the recipe system.
Tests model creation, relationships, constraints, and new columns.
"""

import pytest
from decimal import Decimal
from sqlalchemy import select, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from whati8.models import Food, User
from whati8.models.recipe import Recipe, RecipeIngredient
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.nutrient import Nutrient


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    """Create a test user."""
    from whati8.schemas.auth import UserCreate
    from whati8.services.auth import AuthService
    return await AuthService.create_user(db_session, UserCreate(
        username="recipeuser", email="recipe@test.com", password="testpass123",
    ))


@pytest.fixture
async def sample_foods(db_session: AsyncSession, user: User, seed_test_data) -> list[Food]:
    """Create sample foods for recipe ingredients."""
    foods = []
    for name, cal in [("Flour", 364), ("Sugar", 387), ("Butter", 717)]:
        food = Food(name=name, serving_size=100, unit="g", created_by_user_id=user.id)
        db_session.add(food)
        await db_session.flush()
        
        # Add energy nutrient
        energy = await db_session.scalar(select(Nutrient).where(Nutrient.name == "Energy"))
        if energy:
            db_session.add(FoodNutrient(food_id=food.id, nutrient_id=energy.id, amount_per_serving=cal))
        
        foods.append(food)
    
    await db_session.commit()
    return foods


class TestRecipeModelColumns:
    """Verify Recipe model has all required columns."""

    async def test_recipe_has_servings_column(self, db_session: AsyncSession, user: User):
        """Recipe should have a servings field."""
        recipe = Recipe(
            user_id=user.id,
            name="Test Recipe",
            servings=Decimal("8"),
            serving_unit="bowl",
        )
        db_session.add(recipe)
        await db_session.commit()
        await db_session.refresh(recipe)
        
        assert float(recipe.servings) == 8.0
        assert recipe.serving_unit == "bowl"

    async def test_recipe_servings_defaults(self, db_session: AsyncSession, user: User):
        """Servings should default to 1, serving_unit to 'serving'."""
        recipe = Recipe(user_id=user.id, name="Default Test")
        db_session.add(recipe)
        await db_session.commit()
        await db_session.refresh(recipe)
        
        assert float(recipe.servings) == 1.0
        assert recipe.serving_unit == "serving"

    async def test_recipe_has_current_version(self, db_session: AsyncSession, user: User):
        """Recipe should have current_version field, defaulting to 1."""
        recipe = Recipe(user_id=user.id, name="Version Test")
        db_session.add(recipe)
        await db_session.commit()
        await db_session.refresh(recipe)
        
        assert recipe.current_version == 1

    async def test_recipe_has_current_food_id(self, db_session: AsyncSession, user: User):
        """Recipe should have nullable current_food_id FK."""
        recipe = Recipe(user_id=user.id, name="Food Link Test")
        db_session.add(recipe)
        await db_session.commit()
        await db_session.refresh(recipe)
        
        assert recipe.current_food_id is None  # nullable before materialization


class TestFoodModelColumns:
    """Verify Food model has recipe-related columns."""

    async def test_food_has_recipe_id(self, db_session: AsyncSession, user: User):
        """Food should have nullable recipe_id FK."""
        food = Food(name="Recipe Food", serving_size=100, unit="g", created_by_user_id=user.id)
        db_session.add(food)
        await db_session.commit()
        await db_session.refresh(food)
        
        assert food.recipe_id is None  # nullable for non-recipe foods

    async def test_food_has_recipe_version(self, db_session: AsyncSession, user: User):
        """Food should have nullable recipe_version field."""
        food = Food(name="Versioned Food", serving_size=100, unit="g", created_by_user_id=user.id)
        db_session.add(food)
        await db_session.commit()
        await db_session.refresh(food)
        
        assert food.recipe_version is None

    async def test_food_has_is_recipe_expired(self, db_session: AsyncSession, user: User):
        """Food should have is_recipe_expired boolean, defaulting to False."""
        food = Food(name="Expirable Food", serving_size=100, unit="g", created_by_user_id=user.id)
        db_session.add(food)
        await db_session.commit()
        await db_session.refresh(food)
        
        assert food.is_recipe_expired is False

    async def test_food_recipe_expired_flag(self, db_session: AsyncSession, user: User):
        """Can set is_recipe_expired to True."""
        food = Food(
            name="Old Recipe Food", serving_size=100, unit="g",
            created_by_user_id=user.id, is_recipe_expired=True,
        )
        db_session.add(food)
        await db_session.commit()
        await db_session.refresh(food)
        
        assert food.is_recipe_expired is True


class TestRecipeVersionModel:
    """Verify recipe_versions table and model."""

    async def test_create_recipe_version(self, db_session: AsyncSession, user: User):
        """Can create a recipe version linking recipe to food."""
        from whati8.models.recipe import RecipeVersion
        
        recipe = Recipe(user_id=user.id, name="Versioned Recipe")
        db_session.add(recipe)
        await db_session.flush()
        
        food = Food(
            name="Versioned Recipe", serving_size=100, unit="g",
            created_by_user_id=user.id, recipe_id=recipe.id, recipe_version=1,
        )
        db_session.add(food)
        await db_session.flush()
        
        version = RecipeVersion(recipe_id=recipe.id, version=1, food_id=food.id)
        db_session.add(version)
        await db_session.commit()
        await db_session.refresh(version)
        
        assert version.recipe_id == recipe.id
        assert version.version == 1
        assert version.food_id == food.id

    async def test_recipe_version_unique_constraint(self, db_session: AsyncSession, user: User):
        """Can't create two versions with same (recipe_id, version)."""
        from whati8.models.recipe import RecipeVersion
        
        recipe = Recipe(user_id=user.id, name="Unique Test")
        db_session.add(recipe)
        await db_session.flush()
        
        food1 = Food(name="V1", serving_size=100, unit="g", created_by_user_id=user.id)
        food2 = Food(name="V2", serving_size=100, unit="g", created_by_user_id=user.id)
        db_session.add_all([food1, food2])
        await db_session.flush()
        
        v1 = RecipeVersion(recipe_id=recipe.id, version=1, food_id=food1.id)
        db_session.add(v1)
        await db_session.flush()
        
        v1_dup = RecipeVersion(recipe_id=recipe.id, version=1, food_id=food2.id)
        db_session.add(v1_dup)
        
        with pytest.raises(IntegrityError):
            await db_session.flush()


class TestRecipeIngredientColumns:
    """Verify recipe_ingredients has portion_description column."""

    async def test_ingredient_has_portion_description(
        self, db_session: AsyncSession, user: User, sample_foods: list[Food]
    ):
        """RecipeIngredient should have nullable portion_description."""
        recipe = Recipe(user_id=user.id, name="Ingredient Test")
        db_session.add(recipe)
        await db_session.flush()
        
        ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            food_id=sample_foods[0].id,
            quantity=Decimal("2"),
            unit="cup",
            portion_description="cup (125g)",
        )
        db_session.add(ingredient)
        await db_session.commit()
        await db_session.refresh(ingredient)
        
        assert ingredient.portion_description == "cup (125g)"


class TestRecipeRelationships:
    """Verify model relationships work correctly."""

    async def test_recipe_to_food_relationship(self, db_session: AsyncSession, user: User):
        """Recipe.current_food should resolve to the linked Food."""
        recipe = Recipe(user_id=user.id, name="Rel Test")
        db_session.add(recipe)
        await db_session.flush()
        
        food = Food(
            name="Rel Test", serving_size=100, unit="g",
            created_by_user_id=user.id, recipe_id=recipe.id, recipe_version=1,
        )
        db_session.add(food)
        await db_session.flush()
        
        recipe.current_food_id = food.id
        await db_session.commit()
        await db_session.refresh(recipe)
        
        assert recipe.current_food_id == food.id

    async def test_recipe_ingredients_relationship(
        self, db_session: AsyncSession, user: User, sample_foods: list[Food]
    ):
        """Recipe.ingredients should return all ingredients."""
        recipe = Recipe(user_id=user.id, name="Multi Ingredient")
        db_session.add(recipe)
        await db_session.flush()
        
        for i, food in enumerate(sample_foods):
            ing = RecipeIngredient(
                recipe_id=recipe.id, food_id=food.id,
                quantity=Decimal(str(i + 1)), unit="cup",
            )
            db_session.add(ing)
        
        await db_session.commit()
        
        # Re-fetch with eager loading (async requires selectinload)
        from sqlalchemy.orm import selectinload
        result = await db_session.execute(
            select(Recipe).where(Recipe.id == recipe.id)
            .options(selectinload(Recipe.ingredients))
        )
        loaded = result.scalar_one()
        assert len(loaded.ingredients) == 3

    async def test_recipe_cascade_delete(
        self, db_session: AsyncSession, user: User, sample_foods: list[Food]
    ):
        """Deleting a recipe should cascade-delete its ingredients."""
        recipe = Recipe(user_id=user.id, name="Cascade Delete")
        db_session.add(recipe)
        await db_session.flush()
        
        ing = RecipeIngredient(
            recipe_id=recipe.id, food_id=sample_foods[0].id,
            quantity=Decimal("1"), unit="cup",
        )
        db_session.add(ing)
        await db_session.commit()
        
        recipe_id = recipe.id
        ing_id = ing.recipe_ingredient_id
        
        await db_session.delete(recipe)
        await db_session.commit()
        
        # Ingredient should be gone
        result = await db_session.execute(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_ingredient_id == ing_id
            )
        )
        assert result.scalar_one_or_none() is None

    async def test_user_recipes_relationship(self, db_session: AsyncSession, user: User):
        """User.recipes should return all user's recipes."""
        for name in ["Recipe 1", "Recipe 2"]:
            db_session.add(Recipe(user_id=user.id, name=name))
        await db_session.commit()
        
        from sqlalchemy.orm import selectinload
        result = await db_session.execute(
            select(User).where(User.id == user.id)
            .options(selectinload(User.recipes))
        )
        loaded = result.scalar_one()
        assert len(loaded.recipes) == 2
