"""
Pydantic schemas for user food profile endpoints.

Defines request/response schemas for managing user's personal food library.
"""

from datetime import datetime

from pydantic import Field

from whati8.schemas.base import BaseORMModel, BaseRequestModel, BaseResponseModel
from whati8.schemas.food import FoodResponse


class UserFoodRegister(BaseRequestModel):
    """Request schema for registering a food to user's profile."""

    food_id: int = Field(..., description="ID of the food to register")
    nickname: str | None = Field(None, max_length=100, description="Custom nickname")
    default_quantity: float | None = Field(
        None, gt=0, description="Preferred serving quantity"
    )
    default_unit: str | None = Field(None, max_length=50, description="Preferred unit")
    default_meal_id: int | None = Field(None, description="Default meal category")
    is_favorite: bool = Field(False, description="Pin to favorites")


class UserFoodUpdate(BaseRequestModel):
    """Request schema for updating user food settings (all fields optional)."""

    nickname: str | None = Field(None, max_length=100, description="Custom nickname")
    default_quantity: float | None = Field(
        None, gt=0, description="Preferred serving quantity"
    )
    default_unit: str | None = Field(None, max_length=50, description="Preferred unit")
    default_meal_id: int | None = Field(None, description="Default meal category")
    is_favorite: bool | None = Field(None, description="Pin to favorites")


class MealBasic(BaseORMModel):
    """Basic meal info for user food response."""

    id: int
    name: str


class UserFoodResponse(BaseORMModel):
    """Response schema for a user's registered food."""

    id: int
    user_id: int
    food_id: int
    nickname: str | None
    default_quantity: float | None
    default_unit: str | None
    default_meal_id: int | None
    is_favorite: bool
    use_count: int
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Nested relationships
    food: FoodResponse = Field(..., description="Full food details with nutrients")
    default_meal: MealBasic | None = Field(None, description="Default meal category")


class UserFoodListResponse(BaseResponseModel):
    """Paginated list of user's registered foods."""

    foods: list[UserFoodResponse] = Field(..., description="List of user foods")
    total: int = Field(..., description="Total number of user foods")
    limit: int = Field(..., description="Results per page")
    offset: int = Field(..., description="Result offset for pagination")
