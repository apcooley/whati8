"""
SQLAlchemy models for whati8 application.

All models are imported here to ensure they're discovered by Alembic.
"""

from whati8.models.api_key import ApiKey
from whati8.models.base import Base
from whati8.models.food import Food
from whati8.models.food_log import FoodLog
from whati8.models.food_nutrient import FoodNutrient
from whati8.models.food_portion import FoodPortion
from whati8.models.meal import Meal
from whati8.models.nutrient import Nutrient
from whati8.models.recipe import Recipe, RecipeIngredient, RecipeVersion
from whati8.models.refresh_token import RefreshToken
from whati8.models.user import User
from whati8.models.user_food import UserFood
from whati8.models.user_goal import UserGoal
from whati8.models.user_summary_nutrient import UserSummaryNutrient

__all__ = [
    "ApiKey",
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
    "RecipeVersion",
    "RefreshToken",
    "UserFood",
    "UserGoal",
    "UserSummaryNutrient",
]
