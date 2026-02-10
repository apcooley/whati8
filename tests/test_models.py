"""Tests for database models."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.models import (
    Food,
    FoodLog,
    FoodNutrient,
    Meal,
    Nutrient,
    Recipe,
    RecipeIngredient,
    User,
    UserGoal,
)


@pytest.mark.db
@pytest.mark.unit
class TestUserModel:
    """Test User model."""

    async def test_create_user(self, db_session: AsyncSession):
        """Test creating a user."""
        user = User(
            username="modeltest",
            email="modeltest@example.com",
            password_hash="hashed_password",
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.username == "modeltest"
        assert user.created_at is not None

    async def test_user_unique_username(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test username uniqueness constraint."""
        duplicate_user = User(
            username=test_user.username,  # Duplicate
            email="different@example.com",
            password_hash="hash",
        )
        db_session.add(duplicate_user)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()

    async def test_user_unique_email(self, db_session: AsyncSession, test_user: User):
        """Test email uniqueness constraint."""
        duplicate_user = User(
            username="different",
            email=test_user.email,  # Duplicate
            password_hash="hash",
        )
        db_session.add(duplicate_user)

        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()


@pytest.mark.db
@pytest.mark.unit
class TestNutrientModel:
    """Test Nutrient model."""

    async def test_create_nutrient(self, db_session: AsyncSession):
        """Test creating a nutrient."""
        nutrient = Nutrient(
            name="Vitamin C",
            unit="mg",
            description="Ascorbic acid",
        )
        db_session.add(nutrient)
        await db_session.commit()
        await db_session.refresh(nutrient)

        assert nutrient.id is not None
        assert nutrient.name == "Vitamin C"

    async def test_nutrient_allows_duplicate_names(self, db_session: AsyncSession, seed_test_data):
        """Test that nutrients allow duplicate names (users can define custom nutrients)."""
        # Get existing nutrient
        result = await db_session.execute(select(Nutrient).limit(1))
        existing = result.scalar_one()

        # Same name is allowed (e.g., different users can have custom "Net Carbs")
        duplicate = Nutrient(name=existing.name, unit="g", description="User-defined version")
        db_session.add(duplicate)
        await db_session.commit()  # Should not raise
        await db_session.refresh(duplicate)

        assert duplicate.id is not None
        assert duplicate.id != existing.id


@pytest.mark.db
@pytest.mark.unit
class TestFoodModel:
    """Test Food model."""

    async def test_create_food(self, db_session: AsyncSession):
        """Test creating a food."""
        food = Food(
            name="Test Food",
            brand="Test Brand",
            serving_size=100.0,
            unit="g",
            usda_fdc_id=99999,
        )
        db_session.add(food)
        await db_session.commit()
        await db_session.refresh(food)

        assert food.id is not None
        assert food.name == "Test Food"
        assert food.serving_size == 100.0

    async def test_food_with_nutrients(self, db_session: AsyncSession, seed_test_data):
        """Test food with nutrient relationships via explicit query."""
        # Get existing food
        result = await db_session.execute(select(Food).limit(1))
        food = result.scalar_one()

        # Query food nutrients explicitly (avoid lazy loading issues in async)
        fn_result = await db_session.execute(
            select(FoodNutrient).where(FoodNutrient.food_id == food.id)
        )
        food_nutrients = fn_result.scalars().all()

        assert len(food_nutrients) > 0
        assert food_nutrients[0].food_id == food.id


@pytest.mark.db
@pytest.mark.unit
class TestMealModel:
    """Test Meal model."""

    async def test_create_meal(self, db_session: AsyncSession):
        """Test creating a meal."""
        meal = Meal(name="Second Breakfast")
        db_session.add(meal)
        await db_session.commit()
        await db_session.refresh(meal)

        assert meal.id is not None
        assert meal.name == "Second Breakfast"

    async def test_meal_allows_duplicate_names(self, db_session: AsyncSession, seed_test_data):
        """Test that meals allow duplicate names (users can define custom meals)."""
        # Same name is allowed (e.g., different users can have custom "Brunch")
        duplicate = Meal(name="Breakfast")  # Same as seeded meal
        db_session.add(duplicate)
        await db_session.commit()  # Should not raise
        await db_session.refresh(duplicate)

        assert duplicate.id is not None


@pytest.mark.db
@pytest.mark.unit
class TestFoodLogModel:
    """Test FoodLog model."""

    async def test_create_food_log(
        self, db_session: AsyncSession, test_user: User, seed_test_data
    ):
        """Test creating a food log entry."""
        # Get a food
        food_result = await db_session.execute(select(Food).limit(1))
        food = food_result.scalar_one()

        # Get a meal
        meal_result = await db_session.execute(select(Meal).limit(1))
        meal = meal_result.scalar_one()

        food_log = FoodLog(
            user_id=test_user.id,
            food_id=food.id,
            meal_id=meal.id,
            quantity=2.0,
            logged_at=datetime.utcnow(),
        )
        db_session.add(food_log)
        await db_session.commit()
        await db_session.refresh(food_log)

        assert food_log.id is not None
        assert food_log.user_id == test_user.id
        assert food_log.quantity == 2.0

    async def test_food_log_foreign_keys(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test food log foreign key constraints."""
        # Invalid food_id should fail
        invalid_log = FoodLog(
            user_id=test_user.id,
            food_id=99999,  # Nonexistent
            quantity=1.0,
            logged_at=datetime.utcnow(),
        )
        db_session.add(invalid_log)

        with pytest.raises(Exception):  # Foreign key violation
            await db_session.commit()


@pytest.mark.db
@pytest.mark.unit
class TestUserGoalModel:
    """Test UserGoal model."""

    async def test_create_user_goal(self, db_session: AsyncSession, test_user: User):
        """Test creating a user goal."""
        goal = UserGoal(
            user_id=test_user.id,
            goal_type="calories",
            target_value=2000.0,
            unit="kcal",
        )
        db_session.add(goal)
        await db_session.commit()
        await db_session.refresh(goal)

        assert goal.id is not None
        assert goal.goal_type == "calories"
        assert goal.target_value == 2000.0

    async def test_user_goal_flexible_types(
        self, db_session: AsyncSession, test_user: User
    ):
        """Test flexible goal types (design feature)."""
        # Can create any goal type without schema changes
        goals = [
            UserGoal(
                user_id=test_user.id,
                goal_type="protein",
                target_value=150.0,
                unit="g",
            ),
            UserGoal(
                user_id=test_user.id,
                goal_type="ww_points",
                target_value=23.0,
                unit="points",
            ),
            UserGoal(
                user_id=test_user.id,
                goal_type="water",
                target_value=8.0,
                unit="cups",
            ),
        ]

        for goal in goals:
            db_session.add(goal)

        await db_session.commit()

        # Verify all goals created
        result = await db_session.execute(
            select(UserGoal).where(UserGoal.user_id == test_user.id)
        )
        created_goals = result.scalars().all()
        assert len(created_goals) == 3


@pytest.mark.db
@pytest.mark.unit
class TestRecipeModel:
    """Test Recipe and RecipeIngredient models."""

    async def test_create_recipe(self, db_session: AsyncSession, test_user: User):
        """Test creating a recipe."""
        recipe = Recipe(
            user_id=test_user.id,
            name="Scrambled Eggs",
            description="Simple breakfast",
        )
        db_session.add(recipe)
        await db_session.commit()
        await db_session.refresh(recipe)

        assert recipe.id is not None
        assert recipe.name == "Scrambled Eggs"

    async def test_recipe_with_ingredients(
        self, db_session: AsyncSession, test_user: User, seed_test_data
    ):
        """Test recipe with ingredients."""
        # Get a food
        food_result = await db_session.execute(select(Food).limit(1))
        food = food_result.scalar_one()

        # Create recipe
        recipe = Recipe(
            user_id=test_user.id,
            name="Egg Recipe",
            description="Egg-based dish",
        )
        db_session.add(recipe)
        await db_session.flush()

        # Add ingredient
        ingredient = RecipeIngredient(
            recipe_id=recipe.id,
            food_id=food.id,
            quantity=2.0,
            unit="pieces",
        )
        db_session.add(ingredient)
        await db_session.commit()

        # Verify
        result = await db_session.execute(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)
        )
        ingredients = result.scalars().all()
        assert len(ingredients) == 1
        assert ingredients[0].quantity == 2.0
