"""
SQLAlchemy models for whati8 application.

All models are imported here to ensure they're discovered by Alembic.
"""

from whati8.models.base import Base
from whati8.models.food import Food
from whati8.models.food_log import FoodLog
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.food_portion import FoodPortion
from whati8.models.meal import Meal
from whati8.models.nutrient import Nutrient
from whati8.models.recipe import Recipe, RecipeIngredient
from whati8.models.user import User
from whati8.models.user_goal import UserGoal

__all__ = [
    "Base",
    "User",
    "Food",
    "FoodLog",
    "FoodNutrient",
    "FoodPortion",
    "Meal",
    "Nutrient",
    "Recipe",
    "RecipeIngredient",
    "UserGoal",
]
